# EMV Certification Workbench

A local Python toolkit for practicing payment-terminal **pre-certification evidence preparation**: decode synthetic BER-TLV data, execute explicit assertions, trace requirements to results, and export a reviewable evidence packet.

**Learning project only.** This is not an EMVCo-qualified tool, an accredited laboratory service, a payment kernel, or official certification. A green report means the supplied lab assertions passed; it does not establish EMV compliance. No terminal, acquirer, payment network, or live payment is contacted.

## Quick start

Python 3.10+; runtime and tests use only the standard library. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m emv_workbench decode '77 05 9F36 02 0001'
python3 -m emv_workbench run examples/plan.json --out artifacts/passing
python3 -m emv_workbench run examples/failing-plan.json --out artifacts/failing
```

The passing fixture has two illustrative transactions (purchase and refund), six assertions, and three lab requirements. The failing fixture changes the refund's transaction-type byte while retaining its expectation: the second case fails and the process returns **1**. That failure is intentional. Inspect `artifacts/passing/report.html` in a browser, `report.json` for automation, and `traceability.csv` for requirement coverage.

Exit codes: **0** = all assertions pass and all requirements covered; **1** = an assertion, decode, or coverage failure; **2** = invalid plan, malformed decode command, or file error. Reports in the selected output directory are overwritten on rerun. Choose a fresh directory to retain separate runs.

Optional install for the `emv-workbench` command:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
emv-workbench run examples/plan.json --out artifacts
```

Installation may fetch setuptools from the package registry. Running directly requires no install or internet.

## What it demonstrates

- Recursive, bounded BER-TLV parsing with absolute byte offsets, primitive/constructed nodes, multi-byte tags, definite short/long lengths, and preserved duplicate tags.
- Strict rejection of truncated values, container overruns, indefinite lengths, non-minimal lengths, unsupported padding, oversized tags, and excessive nesting/input.
- JSON plan validation; stable case/assertion identifiers; `count`, `length`, and `equals` checks. Length and equality require exactly one occurrence, so duplicate singleton fields fail explicitly.
- Requirement coverage checks: a declared requirement with no assertion fails the overall run. Coverage records linkage, **not completeness of the underlying specification**.
- Deterministic SHA-256 of canonical JSON to identify the input plan, plus versioned JSON, escaped offline HTML, and spreadsheet-safe traceability CSV.
- Unit and subprocess integration tests including malformed encodings, duplicate tags, absent tags, hash changes, output escaping, and all three exit statuses.

## Plan format

See [examples/plan.json](examples/plan.json) for the complete runnable example. IDs beginning with `LAB-` are invented learning requirements, not official test identifiers.

```json
{
  "version": 1,
  "synthetic": true,
  "requirements": {"LAB-01": "Exactly one transaction-type field"},
  "cases": [{
    "id": "TC-001",
    "title": "Synthetic purchase",
    "tlv": "9C0100",
    "assertions": [
      {"requirement": "LAB-01", "tag": "9C", "op": "count", "expected": 1}
    ]
  }]
}
```

`count` and `length` expect nonnegative integer counts/byte lengths. `equals` expects uppercase whole-byte hexadecimal text. Tags are uppercase hex. Checks search every node recursively, including constructed nodes. There is no path-scoped selection; identical tags in separate templates count as duplicates. Plan versions other than 1 are rejected.

## Architecture and design choices

```text
Synthetic JSON plan
  -> schema validation
  -> bounded BER-TLV tree
  -> assertion engine + coverage matrix
  -> JSON / HTML / CSV evidence packet
```

`tlv.py` owns parsing and structural inventories; `runner.py` owns plan validation, assertions and coverage; `report.py` owns presentation; `__main__.py` owns file access and exit status. Parsing does not read files or make network requests. Reports never serialize TLV values or expected equality values, including values embedded in constructed containers. Inventories retain only tag, offset, byte length and constructed status.

The parser deliberately supports a restricted definite-length BER-TLV subset: maximum 64 KiB decoded input, four tag bytes, three length bytes, and 12 nesting levels. It rejects padding and non-minimal length forms rather than trying to repair data. This strict profile is a project choice, not a universal BER acceptance rule. Unknown tags can be inspected structurally; no full EMV tag dictionary or semantic validator is implied.

A canonical hash makes runs comparable; it is **not a signature, trusted timestamp, or tamper-proof audit trail**. Reports omit timestamps to make identical inputs reproducible. Rule expectations are explicit and reviewable instead of hiding a proprietary certification test set. HTML has no scripts or remote dependencies. The CSV neutralizes formula prefixes in user-controlled identifiers.

## Where this fits in real EMV testing

For acceptance devices, L1 concerns communication interfaces (mechanical/electrical/RF); L2 concerns kernel processing logic. EMVCo defines approval processes and recognizes independent laboratories and qualified tools. See [EMVCo's L1/L2 overview](https://www.emvco.com/news-publications/what-are-emv-level-1-and-level-2-testing/).

L3 concerns integration with merchant/payment infrastructure. Participant Systems provide their test plans; EMVCo defines a testing framework and tool qualification process. See [EMVCo's L3 overview](https://www.emvco.com/news-publications/what-is-level-3-terminal-integration-testing/) and [official L3 technology resources](https://www.emvco.com/emv-technologies/emv-level-3-testing/). These sources informed the project scope; they do not endorse this repository.

This toolkit practices the evidence discipline around such workflows. It performs none of those approval processes. Its TLV fixtures are hand-built synthetic data objects, **not complete APDU exchanges or valid end-to-end EMV transaction transcripts**. It does not calculate or authenticate cryptograms, simulate issuer authorization, evaluate CVM/risk logic, measure RF/electrical performance, or implement payment-system certification suites.

## Data boundaries and limitations

Use only synthetic fixtures. The `synthetic: true` flag is an explicit declaration, not a detector. Do not provide real cardholder data, PANs, track data, PIN blocks, cryptographic keys, or production logs. The decoder accepts arbitrary bytes and cannot determine whether data is sensitive. Values are omitted from generated reports, but the input plan stays on disk; free-text IDs/descriptions are exported. Do not put sensitive information in them. CLI arguments may remain in shell history.

The CLI rejects plan files above 2 MB and bounds case/assertion counts. It is an offline developer utility, not a hardened multi-tenant service. No encryption, secure deletion, access control, or PCI compliance claim is made. Larger datasets, path-scoped matching, schema migrations, and signed evidence bundles would need additional design and testing.

## Validation

Run `python3 -m unittest discover -s tests -v`. GitHub Actions is configured to run the same suite and passing demo on Python 3.10, 3.12 and 3.13. A workflow configuration is not evidence that those remote runs have passed; inspect the repository's Actions tab for current results.

MIT licensed. EMV is a trademark owned by EMVCo, LLC. This project is independent of EMVCo and payment networks.
