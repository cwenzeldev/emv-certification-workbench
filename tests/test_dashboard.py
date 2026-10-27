import http.client
import json
import re
import threading
import unittest
from emv_workbench.dashboard import make_server

class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        _, page = cls.request('GET','/')
        cls.token = re.search(r"const token='([a-f0-9]+)'",page.decode()).group(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    @classmethod
    def request(cls,method,path,payload=None,token=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',cls.server.server_port,timeout=5)
        hs={'Content-Type':'application/json'}
        if token:hs['X-Workbench-Token']=token
        hs.update(headers or {})
        conn.request(method,path,json.dumps(payload) if payload is not None else None,hs)
        response=conn.getresponse();status=response.status;body=response.read();conn.close()
        return status,body

    def test_page(self):
        status,body=self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn(b'Transaction lab',body)
        self.assertNotIn(b'__SESSION_TOKEN__',body)

    def test_sample_run(self):
        _,body=self.request('GET','/api/samples');plan=json.loads(body)
        status,result=self.request('POST','/api/run',plan,self.token)
        self.assertEqual(status,200)
        data=json.loads(result)
        self.assertTrue(data['report']['passed'])
        self.assertIn('Synthetic evidence report',data['html'])

    def test_failure(self):
        _,body=self.request('GET','/api/samples');plan=json.loads(body)
        plan['cases'][1]['tlv']=plan['cases'][1]['tlv'][:-2]+'00'
        status,result=self.request('POST','/api/run',plan,self.token)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(result)['report']['summary']['failed'],1)

    def test_auth_required(self):
        self.assertEqual(self.request('POST','/api/run',{})[0],403)

    def test_host_guard(self):
        self.assertEqual(self.request('GET','/',headers={'Host':'evil.example'})[0],403)

    def test_decode(self):
        status,body=self.request('POST','/api/decode',{'hex':'77059F36020001'},self.token)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['inventory'][1]['tag'],'9F36')
        self.assertNotIn('value',body.decode())

    def test_invalid_decode(self):
        self.assertEqual(self.request('POST','/api/decode',{'hex':'9F'},self.token)[0],400)

    def test_invalid_plan(self):
        self.assertEqual(self.request('POST','/api/run',[],self.token)[0],400)

    def test_no_arbitrary_file(self):
        self.assertEqual(self.request('GET','/../../README.md')[0],404)

if __name__=='__main__':unittest.main()
