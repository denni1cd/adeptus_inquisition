"""Optional offline trace conversion and grading, independent of skill execution."""
import argparse
import json
import sys
from .atif_adapter import export, EvidenceError
from .vally_backend import grade


def main(argv=None):
    p = argparse.ArgumentParser(description="Optional Inquisition trace diagnostics")
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("export-atif")
    for field in ("input", "atif", "provenance"):
        a.add_argument("--" + field, required=True)
    a = sub.add_parser("grade")
    for field in ("atif", "profile", "stimulus", "output"):
        a.add_argument("--" + field, required=True)
    a.add_argument("--vally", default="vally")
    args = p.parse_args(argv)
    try:
        result = (export(args.input, args.atif, args.provenance)
                  if args.action == "export-atif" else
                  grade(args.atif, args.profile, args.output, args.stimulus, args.vally))
        print(json.dumps(result, indent=2))
        return 0
    except (EvidenceError, ValueError, TypeError, OSError) as exc:
        print(json.dumps({"status": "DIAGNOSTIC_UNAVAILABLE", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
