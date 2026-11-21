"""Synthetic policy fixtures. NEVER claim actual workflow runs or independent agents."""
from inquisition.engine import digest
from inquisition.evaluation import audits
from inquisition.evaluation.scoped import QUALITY, compare_scoped


def plan():
    categories = [
        ("original", "origin", "database"), ("transfer", "transfer", "database"),
        ("game", "unrelated", "game"), ("hidden", "holdout", "service"),
        ("known", "established", "utility"),
    ]
    return {
        "protocol_sha256": digest("synthetic protocol"),
        "selection_evidence": "fixture-only independent selection",
        "repetitions": 2,
        "primary_outcome": "repair_cycles",
        "cases": [
            {"case_id": cid, "category": cat, "family": family, "in_scope": True,
             "task_sha256": digest("task-" + cid), "criteria_sha256": digest("criteria-" + cid),
             "hidden_from_reformer": cat == "holdout"}
            for cid, cat, family in categories
        ],
        "metrics": {"repair_cycles": {"direction": "lower", "kind": "efficiency", "tolerance": 0},
                    "quality": {"direction": "higher", "kind": "quality", "tolerance": 0}},
    }


def trials(p, baseline="b"*40, candidate="c"*40):
    rows = []
    for case in p["cases"]:
        for rep in range(1, p["repetitions"] + 1):
            for arm, commit in (("baseline", baseline), ("candidate", candidate)):
                cid = case["case_id"]
                row = {"case_id": cid, "arm": arm, "repetition": rep,
                       "task_sha256": case["task_sha256"], "criteria_sha256": case["criteria_sha256"],
                       "commit": commit, "run_ref": f"synthetic/{cid}/{arm}/{rep}",
                       "run_sha256": digest([cid, rep, arm]),
                       "environment_sha256": digest("matched synthetic environment"),
                       "checks": {k: {"passed": True, "evidence_ref": "synthetic proof"} for k in QUALITY},
                       "contract_alignment_verified": True, "contract_alignment_ref": "synthetic audit",
                       "trace": {"coverage": "PARTIAL", "evidence_ref": "synthetic trace"},
                       "metrics": {"repair_cycles": {"value": 1 if arm == "candidate" else 3,
                                   "evidence_ref": "synthetic counts", "complete": True},
                                   "quality": {"value": 100, "evidence_ref": "synthetic checks", "complete": True}}}
                rows.append(row)
    return rows


def packet(ledger, stage, payload, index=0, verdict="PASS", objections=None, cid="campaign"):
    c = audits.get(ledger, cid)
    i = audits.STAGES.index(stage)
    label = f"fixture-{stage}-{index}"
    return {"stage": stage, "invocation_id": label, "context_id": "context-" + label,
            "trace_ref": label + ".trace", "report_ref": label + ".report",
            "report_sha256": digest(label), "verdict": verdict,
            "answers": {k: "synthetic response " + k for k in audits.QUESTIONS[stage]},
            "objections": objections or [],
            "basis": {"event_packet_hash": ledger.event(c["event_id"])["packet_hash"],
                      "prior": {s: digest(c["current"][s]) for s in audits.STAGES[:i]},
                      "authors": [{"invocation_id": "author-" + stage, "context_id": "author-context-" + stage}],
                      **payload}}


def proposal():
    return {"scope": {"kind": "GENERAL"}, "placement": "core", "hypothesis": "fixture",
            "applicability": "fixture", "counterexample_analysis": "fixture", "complexity_analysis": "fixture"}


def first_stages(ledger, event_id="evt-failure"):
    audits.start(ledger, event_id, "campaign", [
        {"invocation_id": "synthetic-proposer", "context_id": "synthetic-context-proposer"}])
    audits.record(ledger, "campaign", packet(ledger, "diagnosis",
                  {"finding_ref": "synthetic-finding", "finding_sha256": digest("finding")}))
    prop = proposal()
    audits.record(ledger, "campaign", packet(ledger, "generalization",
                  {"proposal": prop, "proposal_sha256": digest(prop)}))
    p = plan()
    audits.record(ledger, "campaign", packet(ledger, "experiment_plan", {"plan": p}))
    return p, prop


def complete(ledger, event_id, manifest):
    p, prop = first_stages(ledger, event_id)
    manifest = dict(manifest, scope=prop["scope"], placement=prop["placement"],
                    audit_campaign="campaign", proposal_sha256=digest(prop), plan_sha256=digest(p))
    candidate = ledger.candidate(event_id, manifest)
    rows = trials(p, manifest["baseline_commit"], manifest["candidate_commit"])
    report = compare_scoped(p, manifest["scope"], manifest["baseline_commit"],
                            manifest["candidate_commit"], rows)
    assert report["status"] == "SUPPORTED_FOR_INDEPENDENT_REVIEW"
    binding = {"candidate_id": manifest["candidate_id"], "manifest_sha256": digest(manifest)}
    audits.record(ledger, "campaign", packet(ledger, "experimental_validity",
                  dict(binding, trials=rows, comparison=report)))
    audits.record(ledger, "campaign", packet(ledger, "final", binding))
    return candidate, audits.campaign_digest(ledger, candidate)
