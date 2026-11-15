"""CLI for the portable Inquisition skill. Offline, deterministic, and stdlib-only."""
import argparse
import json
import os
import sys

from .engine import GateError, Ledger, read_json


def main(argv=None):
    p = argparse.ArgumentParser(prog="inquisition", description="Inquisition V1 evidence ledger")
    p.add_argument("--home", default=".adeptus_inquisition", help="durable state directory")
    sub = p.add_subparsers(dest="action", required=True)

    def cmd(name, *fields):
        q = sub.add_parser(name)
        for flag in fields:
            q.add_argument("--" + flag.replace("_", "-"), required=True)
        return q

    cmd("ingest", "package")
    cmd("finding", "event_id", "finding")
    a = cmd("attempt", "event_id", "issue_id", "hypothesis", "evidence")
    a.add_argument("--outcome", choices=["FAILED", "PENDING"], default="FAILED")
    a.add_argument("--reformer-invocation-id")
    a.add_argument("--reformer-context-id")
    cmd("recover", "event_id", "issue_id", "receipt")
    cmd("milestone", "event_id", "inspection")
    cmd("candidate", "event_id", "manifest")
    cmd("review", "candidate_id", "receipt")
    d = cmd("decide", "candidate_id")
    d.add_argument("--pr-url")
    d.add_argument("--approval", help="JSON file containing explicit, scoped Emperor approval")
    a = cmd("activate", "candidate_id")
    a.add_argument("--receipt", help="signed trusted fresh-Work loader attestation")
    cmd("rollback", "repository")
    cmd("show")
    args = p.parse_args(argv)
    try:
        ledger = Ledger(args.home)
        key = os.environ.get("INQUISITION_TRUST_KEY")
        if args.action == "ingest":
            result = ledger.ingest(read_json(args.package))
        elif args.action == "finding":
            result = ledger.record_finding(args.event_id, read_json(args.finding))
        elif args.action == "attempt":
            result = ledger.attempt(args.event_id, args.issue_id, args.hypothesis,
                                    args.evidence, args.outcome,
                                    args.reformer_invocation_id, args.reformer_context_id)
        elif args.action == "recover":
            result = ledger.resolve_recovery(args.event_id, args.issue_id, args.receipt, key)
        elif args.action == "milestone":
            result = ledger.close_milestone(args.event_id, read_json(args.inspection))
        elif args.action == "candidate":
            result = ledger.candidate(args.event_id, read_json(args.manifest))
        elif args.action == "review":
            result = ledger.review(args.candidate_id, read_json(args.receipt), key)
        elif args.action == "decide":
            approval = read_json(args.approval) if args.approval else None
            result = ledger.decide(args.candidate_id, args.pr_url, approval, key)
        elif args.action == "activate":
            result = ledger.activate(args.candidate_id,
                                     read_json(args.receipt) if args.receipt else None, key)
        elif args.action == "rollback":
            result = ledger.rollback(args.repository)
        else:
            result = ledger.data
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateError, KeyError, ValueError, OSError) as error:
        print(json.dumps({"state": "BLOCKED", "reason": str(error)}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
