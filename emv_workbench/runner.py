"""Validate an explicit synthetic plan and retain assertion-level traceability."""
import hashlib
import json
import re
from .tlv import decode, flatten, inventory, DecodeError

class PlanError(ValueError):
    pass


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise PlanError(f"{label} must be nonempty text, at most 200 characters")
    return value


def validate(plan):
    if not isinstance(plan, dict) or plan.get("synthetic") is not True or plan.get("version") != 1:
        raise PlanError("Plan requires version 1 and synthetic: true")
    requirements = plan.get("requirements")
    cases = plan.get("cases")
    if not isinstance(requirements, dict) or not requirements or len(requirements) > 100:
        raise PlanError("Provide 1–100 requirements")
    for key, value in requirements.items():
        _text(key, "Requirement ID")
        _text(value, "Requirement description")
    if not isinstance(cases, list) or not cases or len(cases) > 500:
        raise PlanError("Provide 1–500 cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise PlanError("Each case must be an object")
        cid = _text(case.get("id"), "Case ID")
        _text(case.get("title"), "Case title")
        if cid in seen:
            raise PlanError("Duplicate case ID")
        seen.add(cid)
        if not isinstance(case.get("tlv"), str) or len(case["tlv"]) > 200000:
            raise PlanError("Case TLV must be bounded text")
        checks = case.get("assertions")
        if not isinstance(checks, list) or not checks or len(checks) > 100:
            raise PlanError("Each case needs 1–100 assertions")
        for check in checks:
            if (not isinstance(check, dict) or not isinstance(check.get("requirement"), str)
                    or check["requirement"] not in requirements):
                raise PlanError("Assertion refers to unknown requirement")
            if not isinstance(check.get("tag"), str) or not re.fullmatch(r"(?:[0-9A-F]{2}){1,4}", check["tag"]):
                raise PlanError("Assertion tag must be 1–4 uppercase hex bytes")
            op = check.get("op")
            val = check.get("expected")
            if op in ("count", "length"):
                if type(val) is not int or not 0 <= val <= 65536:
                    raise PlanError("Count/length expected must be a nonnegative integer")
            elif op == "equals":
                if not isinstance(val, str) or not re.fullmatch(r"(?:[0-9A-F]{2})*", val) or len(val) > 131072:
                    raise PlanError("Equality expected must be uppercase whole hex bytes")
            else:
                raise PlanError("Supported operations: count, length, equals")
    return plan


def run(plan):
    validate(plan)
    results = []
    coverage = {rid: [] for rid in plan["requirements"]}
    for case in plan["cases"]:
        error = None
        try:
            nodes = decode(case["tlv"])
            entries = flatten(nodes)
        except DecodeError as exc:
            nodes, entries, error = (), [], str(exc)
        checks = []
        for idx, assertion in enumerate(case["assertions"], 1):
            matches = [n for n in entries if n.tag == assertion["tag"]]
            op, expected = assertion["op"], assertion["expected"]
            if error:
                passed, reason = False, "TLV decode failed"
            elif op == "count":
                passed = len(matches) == expected
                reason = f"Found {len(matches)} occurrence(s); expected {expected}"
            elif len(matches) != 1:
                passed, reason = False, f"Requires exactly one occurrence; found {len(matches)}"
            elif op == "length":
                passed = len(matches[0].value) == expected
                reason = f"Length {len(matches[0].value)}; expected {expected}"
            else:
                passed = matches[0].value.hex().upper() == expected
                reason = "Value matches" if passed else "Value differs (values omitted)"
            rid = assertion["requirement"]
            check = {"id": f"{case['id']}.{idx}", "requirement": rid,
                     "tag": assertion["tag"], "operation": op, "passed": passed, "reason": reason}
            checks.append(check)
            coverage[rid].append(check["id"])
        results.append({"id": case["id"], "title": case["title"],
                        "passed": all(c["passed"] for c in checks), "decode_error": error,
                        "inventory": inventory(nodes), "assertions": checks})
    uncovered = [rid for rid, checks in coverage.items() if not checks]
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"tool_version": "1.0.0", "synthetic": True, "plan_sha256": digest,
            "scope": "Learning/pre-certification evidence only; not official certification",
            "passed": all(c["passed"] for c in results) and not uncovered,
            "summary": {"cases": len(results), "passed": sum(c["passed"] for c in results),
                        "failed": sum(not c["passed"] for c in results)},
            "requirements": plan["requirements"], "coverage": coverage,
            "uncovered_requirements": uncovered, "cases": results}
