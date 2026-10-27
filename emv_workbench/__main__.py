import argparse
import json
import sys
from pathlib import Path
from .tlv import decode, inventory, DecodeError
from .runner import run, PlanError
from .report import write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic TLV pre-certification evidence toolkit")
    commands = parser.add_subparsers(dest="command", required=True)
    decoder = commands.add_parser("decode", help="Inspect structure without exporting values")
    decoder.add_argument("hex", help="Synthetic hex TLV")
    runner = commands.add_parser("run", help="Execute a synthetic JSON plan")
    runner.add_argument("plan", type=Path)
    runner.add_argument("--out", type=Path, default=Path("artifacts"))
    dashboard = commands.add_parser("serve", help="Open a local interactive dashboard")
    dashboard.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from .dashboard import serve
            serve(args.port)
            return 0
        if args.command == "decode":
            print(json.dumps(inventory(decode(args.hex)), indent=2))
            return 0
        if args.plan.stat().st_size > 2_000_000:
            raise PlanError("Plan exceeds 2 MB")
        report = run(json.loads(args.plan.read_text(encoding="utf-8")))
        write_report(report, args.out)
        print(json.dumps({"overall_passed": report["passed"], **report["summary"], "output": str(args.out)}))
        return 0 if report["passed"] else 1
    except (DecodeError, PlanError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Do not echo invalid input, JSON snippets, or raw values.
        print(f"Input/output error ({type(exc).__name__}); check plan schema, TLV structure and paths", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
