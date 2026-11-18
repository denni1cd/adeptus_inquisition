"""Standalone offline evaluation CLI. No model runner or paid SDK required."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .atif_adapter import EvidenceError, export
from .comparison import compare
from .ledger_bridge import attach
from .vally_backend import grade


def main(argv=None):
    parser = argparse.ArgumentParser(prog="inquisition-evaluation")
    actions = parser.add_subparsers(dest="action", required=True)
    p = actions.add_parser("export-atif", help="Convert evidence envelope to ATIF + provenance")
    p.add_argument("--input", required=True)
    p.add_argument("--atif", required=True)
    p.add_argument("--provenance", required=True)
    p = actions.add_parser("grade", help="Run offline Vally grade, never vally eval")
    p.add_argument("--atif", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--stimulus", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--vally", default="vally")
    p = actions.add_parser("compare", help="Compare paired measured workflows, advisory only")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p = actions.add_parser("attach", help="Attach evidence to paused event without approval")
    p.add_argument("--home", required=True)
    p.add_argument("--event-id", required=True)
    p.add_argument("--provenance", required=True)
    p.add_argument("--grade", required=True)
    p.add_argument("--comparison", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "export-atif":
            result = export(args.input, args.atif, args.provenance)
        elif args.action == "grade":
            result = grade(args.atif, args.profile, args.output, args.stimulus, args.vally)
        elif args.action == "attach":
            result = attach(args.home, args.event_id, args.provenance,
                            args.grade, args.comparison)
        else:
            result = compare(json.loads(Path(args.input).read_text(encoding="utf-8")))
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (EvidenceError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
