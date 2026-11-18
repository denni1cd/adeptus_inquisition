"""Conservative paired workflow comparison. Never authorizes adoption.

Inputs are normalized, independently inspected quality/metric evidence from
real baseline and candidate executions; a Vally score alone is insufficient.
"""
from __future__ import annotations

from statistics import mean

from .atif_adapter import EvidenceError

DIRECTIONS = {"lower", "higher"}


def _rows(rows, variant):
    if not isinstance(rows, list) or not rows:
        raise EvidenceError(variant + " requires actual trials")
    mapped = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise EvidenceError("trial requires case_id")
        key = row["case_id"]
        if not key or key in mapped:
            raise EvidenceError("blank or duplicate case_id in " + variant)
        mapped[key] = row
    return mapped


def _check(record, name):
    entry = record.get("checks", {}).get(name)
    if not isinstance(entry, dict) or type(entry.get("passed")) is not bool:
        raise EvidenceError("missing quality gate " + name)
    if not isinstance(entry.get("evidence_ref"), str) or not entry["evidence_ref"]:
        raise EvidenceError("unreferenced quality gate " + name)
    return entry["passed"]


def _metric(record, metric):
    entry = record.get("metrics", {}).get(metric)
    if not isinstance(entry, dict) or entry.get("complete") is not True:
        raise EvidenceError("incomplete metric " + metric)
    value = entry.get("value")
    if type(value) not in (int, float) or not -1e15 < value < 1e15:
        raise EvidenceError("invalid numeric metric " + metric)
    if not isinstance(entry.get("evidence_ref"), str) or not entry["evidence_ref"]:
        raise EvidenceError("unreferenced metric " + metric)
    return value


def compare(plan):
    """Return a recommendation candidate, not a formal independent approval."""
    if plan.get("schema_version") != "INQUISITION-COMPARISON-v1":
        raise EvidenceError("unsupported comparison schema")
    if not all(isinstance(plan.get(k), str) and plan[k].strip()
               for k in ("branch", "baseline_commit", "candidate_commit", "criteria_hash")):
        raise EvidenceError("branch, commits, and frozen criteria hash required")
    if plan["baseline_commit"] == plan["candidate_commit"]:
        raise EvidenceError("baseline and candidate must have different version pins")
    directions = plan.get("metric_directions")
    if not isinstance(directions, dict) or not directions or any(
        d not in DIRECTIONS for d in directions.values()
    ):
        raise EvidenceError("metric_directions must declare lower/higher")
    original = _rows(plan.get("baseline"), "baseline")
    updated = _rows(plan.get("candidate"), "candidate")
    if set(original) != set(updated):
        raise EvidenceError("case identity mismatch: cannot pair experimental results")
    holdout = [k for k in original if original[k].get("holdout") is True
               and updated[k].get("holdout") is True]
    if not holdout or len(original) < 2:
        raise EvidenceError("at least two paired cases including a holdout required")
    if any(original[k].get("holdout") != updated[k].get("holdout") for k in original):
        raise EvidenceError("holdout designation changed between versions")
    for rows in (original, updated):
        for row in rows.values():
            if not isinstance(row.get("vally_grade_ref"), str) or not row["vally_grade_ref"]:
                raise EvidenceError("Vally grade evidence reference required")
    gate_names = ("original_acceptance", "regressions_clear", "independent_review")
    baseline_ok, candidate_ok = {}, {}
    for case in original:
        baseline_ok[case] = all([_check(original[case], name) for name in gate_names])
        candidate_ok[case] = all([_check(updated[case], name) for name in gate_names])
    damaged = [case for case in original if not candidate_ok[case]]
    if damaged:
        return {"status": "REJECT_CANDIDATE", "reason": "candidate fails mandatory gates",
                "failed_cases": damaged, "approval": False}
    # Baseline deficits are recorded but not forgiven by weakening the criteria.
    repaired = [case for case in original if not baseline_ok[case] and candidate_ok[case]]
    deltas = {}
    better, worse = [], []
    for metric, direction in directions.items():
        before = mean(_metric(original[k], metric) for k in original)
        after = mean(_metric(updated[k], metric) for k in original)
        delta = after - before
        deltas[metric] = {"baseline_mean": before, "candidate_mean": after,
                          "change": delta, "direction": direction}
        if (delta < 0 and direction == "lower") or (delta > 0 and direction == "higher"):
            better.append(metric)
        if (delta > 0 and direction == "lower") or (delta < 0 and direction == "higher"):
            worse.append(metric)
    if worse:
        status = "TRADEOFF_REQUIRES_REVIEW"
    elif better or repaired:
        status = "SUPPORTED_FOR_INDEPENDENT_REVIEW"
    else:
        status = "NO_IMPROVEMENT_DEMONSTRATED"
    return {
        "status": status, "branch": plan["branch"], "paired_cases": len(original),
        "holdout_cases": holdout, "repaired_cases": repaired,
        "improved_metrics": better, "worsened_metrics": worse, "metric_comparison": deltas,
        "approval": False, "note": "Advisory only. Sources and grader authenticity require "
        "independent inspection; original Inquisition governance remains authoritative."
    }
