import copy, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from emv_workbench.tlv import decode, flatten, inventory, DecodeError
from emv_workbench.runner import run, PlanError
from emv_workbench.report import render_html, write_report
ROOT = Path(__file__).resolve().parents[1]

def plan():
    return json.loads((ROOT / 'examples/plan.json').read_text())

class DecoderTests(unittest.TestCase):

    def test_nested_offsets(self):
        self.assertEqual([(x.tag, x.offset, len(x.value)) for x in flatten(decode('77 05 9F36 02 0001'))], [('77', 0, 5), ('9F36', 2, 2)])

    def test_repeated_tags(self):
        self.assertEqual(len(decode('9C01009C0120')), 2)

    def test_long_length(self):
        self.assertEqual(len(decode('538180' + 'AA' * 128)[0].value), 128)

    def test_zero_primitive(self):
        self.assertEqual(decode('5300')[0].value, b'')

    def test_empty_constructed(self):
        self.assertEqual(decode('7700')[0].children, ())

    def test_three_byte_tag(self):
        self.assertEqual(decode('DF81010100')[0].tag, 'DF8101')

    def test_whitespace(self):
        self.assertEqual(decode('9c\n01\t00')[0].tag, '9C')

    def test_malformed_inputs(self):
        for text in ['', '0', 'ZZ', '9F', '9F800100', '9C', '9C02AA', '7780', '53817FAA', '53820080' + 'AA' * 128, '77039C0200', '00', 'FF', '9F8181810100', '5384FFFFFFFF']:
            with self.subTest(text=text[:20]):
                with self.assertRaises(DecodeError):
                    decode(text)

    def test_size_limit(self):
        with self.assertRaises(DecodeError):
            decode('5301FF', max_bytes=2)

    def test_depth_limit(self):
        with self.assertRaises(DecodeError):
            decode('770477027700', max_depth=1)

    def test_inventory_no_values(self):
        self.assertNotIn('ABCDEF', json.dumps(inventory(decode('77055303ABCDEF'))))
        self.assertEqual(inventory(decode('5301AB'))[0]['length'], 1)

class RunnerTests(unittest.TestCase):

    def test_happy_path(self):
        r = run(plan())
        self.assertTrue(r['passed'])
        self.assertEqual(r['summary'], {'cases': 2, 'passed': 2, 'failed': 0})
        self.assertEqual(r['coverage']['LAB-03'], ['TC-001.3', 'TC-002.3'])

    def test_failure_explained(self):
        p = plan()
        p['cases'][0]['assertions'][2]['expected'] = '20'
        r = run(p)
        self.assertFalse(r['passed'])
        self.assertEqual(r['cases'][0]['assertions'][2]['reason'], 'Value differs (values omitted)')

    def test_decode_failure(self):
        p = plan()
        p['cases'][0]['tlv'] = '9C02FF'
        r = run(p)
        self.assertFalse(r['passed'])
        self.assertIsNotNone(r['cases'][0]['decode_error'])

    def test_missing_tag(self):
        p = plan()
        p['cases'][0]['assertions'][0]['tag'] = '5F2A'
        self.assertFalse(run(p)['passed'])

    def test_duplicate_singleton(self):
        p = plan()
        p['cases'][0]['tlv'] = '9C01009C0100'
        self.assertFalse(run(p)['cases'][0]['assertions'][2]['passed'])

    def test_absence(self):
        p = plan()
        p['cases'][0]['assertions'][0].update(tag='5A', op='count', expected=0)
        self.assertTrue(run(p)['passed'])

    def test_uncovered(self):
        p = plan()
        p['requirements']['LAB-04'] = 'Unimplemented'
        r = run(p)
        self.assertFalse(r['passed'])
        self.assertEqual(r['uncovered_requirements'], ['LAB-04'])

    def test_hash(self):
        p = plan()
        r = run(p)
        self.assertEqual(r['plan_sha256'], run(dict(reversed(list(p.items()))))['plan_sha256'])
        p['cases'][0]['title'] = 'Changed'
        self.assertNotEqual(r['plan_sha256'], run(p)['plan_sha256'])

    def test_no_values(self):
        p = plan()
        p['cases'][0]['tlv'] = '5304DEADBEEF'
        p['cases'][0]['assertions'][0].update(tag='53', op='equals', expected='DEADBEEF')
        self.assertNotIn('DEADBEEF', json.dumps(run(p)))

    def test_invalid_schema(self):
        mutations = [lambda p: p.update(synthetic=False), lambda p: p.update(cases=[]), lambda p: p['cases'].append(copy.deepcopy(p['cases'][0])), lambda p: p['cases'][0]['assertions'][0].update(requirement='UNKNOWN'), lambda p: p['cases'][0]['assertions'][0].update(op='exec'), lambda p: p['cases'][0]['assertions'][0].update(expected=True), lambda p: p['cases'][0]['assertions'][0].update(tag='9f02'), lambda p: p['cases'][0]['assertions'][0].update(op='equals', expected='ABC'), lambda p: p.update(requirements={}), lambda p: p['cases'][0].update(assertions=[])]
        for mutate in mutations:
            p = plan()
            mutate(p)
            with self.subTest(mutation=mutations.index(mutate)):
                with self.assertRaises(PlanError):
                    run(p)

    def test_unhashable_requirement(self):
        p = plan()
        p['cases'][0]['assertions'][0]['requirement'] = []
        with self.assertRaises(PlanError):
            run(p)

    def test_nonobject(self):
        with self.assertRaises(PlanError):
            run([])

    def test_unchanged(self):
        p = plan()
        before = copy.deepcopy(p)
        run(p)
        self.assertEqual(p, before)

class ReportCliTests(unittest.TestCase):

    def test_html_escape(self):
        p = plan()
        p['requirements']['LAB-01'] = '<script>alert(1)</script>'
        h = render_html(run(p))
        self.assertNotIn('<script>', h)
        self.assertIn('&lt;script&gt;', h)

    def test_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_report(run(plan()), tmp)
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, {'report.html', 'report.json', 'traceability.csv'})
            self.assertTrue(json.loads((Path(tmp) / 'report.json').read_text())['passed'])

    def test_csv_formula(self):
        p = plan()
        p['requirements']['=1+1'] = p['requirements'].pop('LAB-01')
        for c in p['cases']:
            c['assertions'][0]['requirement'] = '=1+1'
        with tempfile.TemporaryDirectory() as tmp:
            write_report(run(p), tmp)
            self.assertIn("'=1+1", (Path(tmp) / 'traceability.csv').read_text())

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'emv_workbench', *args], cwd=ROOT, capture_output=True, text=True)

    def test_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.cli('run', 'examples/plan.json', '--out', tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_assertion_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.cli('run', 'examples/failing-plan.json', '--out', tmp)
            self.assertEqual(r.returncode, 1, r.stderr)

    def test_missing_file(self):
        self.assertEqual(self.cli('run', 'nonexistent.json').returncode, 2)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'bad.json'
            file.write_text('SECRET-NOT-JSON')
            r = self.cli('run', str(file))
            self.assertEqual(r.returncode, 2)
            self.assertNotIn('SECRET', r.stderr)

    def test_decode(self):
        r = self.cli('decode', '9C0120')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('value', r.stdout)

    def test_invalid_decode(self):
        self.assertEqual(self.cli('decode', '9C02').returncode, 2)
if __name__ == '__main__':
    unittest.main()
