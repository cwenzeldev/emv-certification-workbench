"""Portable offline reports with no scripts or external resources."""
import csv
import html
import io
import json
from pathlib import Path


def render_html(report):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = []
    for case in report["cases"]:
        for check in case["assertions"]:
            rows.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in
                (case["id"], check["id"], check["requirement"], check["tag"],
                 "PASS" if check["passed"] else "FAIL", check["reason"])) + "</tr>")
    requirements = "".join(f"<li><b>{esc(rid)}</b>: {esc(desc)} — "
        f"{esc(', '.join(report['coverage'][rid]) or 'UNCOVERED')}</li>"
        for rid, desc in report["requirements"].items())
    errors = "".join(f"<li>{esc(c['id'])}: {esc(c['decode_error'])}</li>"
                     for c in report["cases"] if c["decode_error"])
    status = "PASS" if report["passed"] else "FAIL"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synthetic evidence report</title><style>
body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#192b36}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #bac8d0;padding:10px;text-align:left}}
th{{background:#edf2f5}}code{{overflow-wrap:anywhere}}li{{margin:10px 0}}
</style><h1>Synthetic evidence report — {status}</h1><p>{esc(report['scope'])}</p>
<p>{esc(report['summary'])}</p><p>Canonical plan SHA-256: <code>{esc(report['plan_sha256'])}</code></p>
<h2>Requirement traceability</h2><ul>{requirements}</ul><h2>Assertions</h2><table>
<tr><th>Case</th><th>Assertion</th><th>Requirement</th><th>Tag</th><th>Result</th><th>Reason</th></tr>
{''.join(rows)}</table><h2>Decode errors</h2><ul>{errors}</ul>
<p>Raw values are omitted. A hash links this report to its input; it is not a digital signature.</p></html>"""


def write_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (directory / "report.html").write_text(render_html(report), encoding="utf-8")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["requirement", "assertion_ids", "covered"])
    for rid, ids in report["coverage"].items():
        # Neutralize spreadsheet formulas in user-controlled IDs.
        cell = "'" + rid if rid[:1] in "=+-@\t\r" else rid
        refs = ";".join(ids)
        if refs[:1] in "=+-@\t\r":
            refs = "'" + refs
        writer.writerow([cell, refs, bool(ids)])
    (directory / "traceability.csv").write_text(buffer.getvalue(), encoding="utf-8")
