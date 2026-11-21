"""Scope policy and prospective, case-level comparison; never authorizes adoption."""
from __future__ import annotations
import re
from .atif_adapter import EvidenceError

SCOPES = ("GENERAL", "DOMAIN", "TASK")
GENERAL_CATEGORIES = {"origin", "transfer", "unrelated", "holdout", "established"}
CATEGORIES = GENERAL_CATEGORIES | {"negative_control"}
QUALITY = ("original_acceptance", "regressions_clear", "independent_review",
           "no_false_pass", "no_capability_loss")
HEX = re.compile(r"[0-9a-f]{64}")


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def scope(value=None):
    if value is None:
        return {"kind": "GENERAL"}
    require(isinstance(value, dict), "scope must be an object")
    kind = value.get("kind")
    require(kind in SCOPES, "unknown improvement scope")
    if kind == "GENERAL":
        require(set(value) == {"kind"}, "GENERAL has no target restriction")
    else:
        require(set(value) == {"kind", "target"} and nonempty(value["target"]),
                "restricted scope requires an explicit target")
    return dict(value)


def validate_proposal(directive, proposal):
    requested = scope(directive)
    actual = scope(proposal.get("scope"))
    require(requested["kind"] == "GENERAL" or requested == actual,
            "cannot widen or redirect a restricted directive without new authorization")
    placement = proposal.get("placement")
    expected = "core" if actual["kind"] == "GENERAL" else "conditional"
    require(placement == expected, "restricted changes must be conditional, not core-wide")
    require(nonempty(proposal.get("hypothesis")) and nonempty(proposal.get("applicability"))
            and nonempty(proposal.get("counterexample_analysis"))
            and nonempty(proposal.get("complexity_analysis")),
            "hypothesis, applicability, counterexamples and complexity analysis required")
    if actual != requested:
        require(nonempty(proposal.get("scope_rationale")),
                "explain why the recommendation is narrower than the directive")
    return actual


def validate_plan(plan, actual):
    """Validate frozen diversity, not semantic truth of all case classifications."""
    require(isinstance(plan, dict) and isinstance(plan.get("cases"), list),
            "frozen benchmark cases required")
    require(sha(plan.get("protocol_sha256")) and nonempty(plan.get("selection_evidence")),
            "frozen protocol hash and independent selection evidence required")
    require(type(plan.get("repetitions")) is int and plan["repetitions"] >= 2,
            "at least two paired repetitions per distinct task required")
    cases = {}
    hashes = set()
    for row in plan["cases"]:
        require(isinstance(row, dict), "invalid case")
        cid, category = row.get("case_id"), row.get("category")
        require(nonempty(cid) and ":" not in cid and cid not in cases, "duplicate or blank case identity")
        require(sha(row.get("task_sha256")) and row["task_sha256"] not in hashes,
                "distinct task content hashes required; repetitions are not tasks")
        require(sha(row.get("criteria_sha256")) and nonempty(row.get("family"))
                and category in CATEGORIES and type(row.get("in_scope")) is bool,
                "case metadata incomplete")
        require(row.get("hidden_from_reformer") is True if category == "holdout" else True,
                "holdout must be independently selected and concealed")
        if actual["kind"] == "GENERAL":
            require(row["in_scope"], "general scope covers all benchmark cases")
        elif category in {"origin", "transfer", "holdout"}:
            require(row["in_scope"], "target and transfer/holdout cases must exercise scope")
        elif category in {"unrelated", "negative_control"}:
            require(not row["in_scope"], "negative controls must be outside restricted scope")
        cases[cid] = row
        hashes.add(row["task_sha256"])
    categories = {r["category"] for r in cases.values()}
    require(GENERAL_CATEGORIES <= categories, "origin, transfer, unrelated, holdout and established cases required")
    if actual["kind"] == "GENERAL":
        require(len({r["family"] for r in cases.values()}) >= 3,
                "general change must cover at least three task families")
        origin_families = {r["family"] for r in cases.values() if r["category"] == "origin"}
        require(any(r["category"] == "unrelated" and r["family"] not in origin_families
                    for r in cases.values()), "unrelated case must differ in task family")
    else:
        require(any(not r["in_scope"] for r in cases.values()),
                "conditional change requires an out-of-scope control")
    measures = plan.get("metrics")
    require(isinstance(measures, dict), "frozen metrics object required (may be empty)")
    for name, m in measures.items():
        require(nonempty(name) and name not in QUALITY, "ambiguous metric identity")
        require(isinstance(m, dict) and m.get("direction") in ("lower", "higher")
                and m.get("kind") in ("quality", "efficiency")
                and type(m.get("tolerance")) in (float, int)
                and 0 <= m["tolerance"] < 1e15,
                "metric direction, kind and materiality tolerance required: " + name)
    return cases


def compare_scoped(plan, actual_scope, baseline_commit, candidate_commit, trials):
    """Compare every matched trial; never let averages hide capability regression."""
    actual_scope = scope(actual_scope)
    cases = validate_plan(plan, actual_scope)
    require(nonempty(baseline_commit) and nonempty(candidate_commit)
            and baseline_commit != candidate_commit, "distinct pinned workflow versions required")
    require(isinstance(trials, list), "actual paired trial records required")
    rows = {}
    for row in trials:
        require(isinstance(row, dict), "invalid trial row")
        cid, arm, rep = row.get("case_id"), row.get("arm"), row.get("repetition")
        require(cid in cases and arm in ("baseline", "candidate") and type(rep) is int
                and 1 <= rep <= plan["repetitions"], "invalid case/arm/repetition")
        key = (cid, arm, rep)
        require(key not in rows, "duplicate trial")
        c = cases[cid]
        require(row.get("task_sha256") == c["task_sha256"] and
                row.get("criteria_sha256") == c["criteria_sha256"],
                "task or acceptance criteria changed")
        require(row.get("commit") == (baseline_commit if arm == "baseline" else candidate_commit),
                "workflow pin mismatch")
        require(nonempty(row.get("run_ref")) and sha(row.get("run_sha256"))
                and sha(row.get("environment_sha256")), "run, digest and environment required")
        # Vally is optional, but any use must disclose observed trace coverage.
        trace = row.get("trace")
        require(isinstance(trace, dict) and trace.get("coverage") in ("PARTIAL", "DECLARED_COMPLETE_NOT_AUTHENTICATED", "UNAVAILABLE")
                and nonempty(trace.get("evidence_ref")), "trace coverage and evidence required")
        if trace.get("vally_grade_ref"):
            require(trace["coverage"] != "UNAVAILABLE" and nonempty(trace["vally_grade_ref"]),
                    "Vally grade requires recorded trajectory evidence")
        checks = row.get("checks", {})
        for check in QUALITY:
            val = checks.get(check, {})
            require(type(val.get("passed")) is bool and nonempty(val.get("evidence_ref")),
                    "unverified mandatory quality check: " + check)
        require(type(row.get("contract_alignment_verified")) is bool
                and nonempty(row.get("contract_alignment_ref")), "independent contract audit required")
        require(row["contract_alignment_verified"], "test/contract discrepancy blocks comparison; refreeze and rerun both arms")
        if actual_scope["kind"] != "GENERAL":
            require(type(row.get("conditional_guidance_applied")) is bool
                    and nonempty(row.get("conditional_evidence_ref")), "conditional invocation evidence required")
            require(row["conditional_guidance_applied"] == (arm == "candidate" and c["in_scope"]),
                    "conditional guidance leaked or failed to load")
        for name in plan["metrics"]:
            m = row.get("metrics", {}).get(name, {})
            require(m.get("complete") is True and type(m.get("value")) in (int, float)
                    and -1e15 < m["value"] < 1e15 and nonempty(m.get("evidence_ref")),
                    "missing/incomplete metric: " + name)
        rows[key] = row
    require(len(rows) == len(cases) * plan["repetitions"] * 2, "matched experiments incomplete")
    require(len({r["run_ref"] for r in rows.values()}) == len(rows), "duplicate run reference")
    require(len({r["run_sha256"] for r in rows.values()}) == len(rows),
            "duplicate run artifact cannot count as another trial")
    failures, gains, tradeoffs, pairs = [], [], [], []
    for cid, case in cases.items():
        for rep in range(1, plan["repetitions"] + 1):
            b, c = rows[cid, "baseline", rep], rows[cid, "candidate", rep]
            pair = f"{cid}:{rep}"
            require(b["environment_sha256"] == c["environment_sha256"],
                    "unmatched experimental environment: " + pair)
            for check in QUALITY:
                bp, cp = b["checks"][check]["passed"], c["checks"][check]["passed"]
                if not cp:
                    failures.append(f"{pair}:{check}")
                elif not bp and cp and case["in_scope"]:
                    gains.append(f"{pair}:{check}")
            deltas = {}
            for name, m in plan["metrics"].items():
                before, after = b["metrics"][name]["value"], c["metrics"][name]["value"]
                delta = (after - before) * (1 if m["direction"] == "higher" else -1)
                deltas[name] = {"baseline": before, "candidate": after, "benefit": delta}
                if delta < -m["tolerance"]:
                    (failures if m["kind"] == "quality" else tradeoffs).append(f"{pair}:{name}")
                elif delta > m["tolerance"] and case["in_scope"]:
                    gains.append(f"{pair}:{name}")
            pairs.append({"case_id": cid, "repetition": rep, "metrics": deltas})
    # Reproducibility requires improvement in every repetition for at least two
    # distinct in-scope cases (not merely a single originating task).
    reproducible = []
    for cid, case in cases.items():
        if not case["in_scope"]:
            continue
        repeated = [set(g.split(":", 2)[2] for g in gains if g.startswith(f"{cid}:{r}:"))
                    for r in range(1, plan["repetitions"] + 1)]
        if set.intersection(*repeated):
            reproducible.append(cid)
    if failures:
        status = "REJECT_CANDIDATE"
    elif tradeoffs:
        status = "TRADEOFF_REQUIRES_REVIEW"
    elif len(reproducible) >= 2 and any(cases[c]["category"] != "origin" for c in reproducible):
        status = "SUPPORTED_FOR_INDEPENDENT_REVIEW"
    else:
        status = "NO_IMPROVEMENT_DEMONSTRATED"
    return {"status": status, "approval": False, "scope": actual_scope,
            "baseline_commit": baseline_commit, "candidate_commit": candidate_commit,
            "distinct_tasks": len(cases), "paired_trials": len(pairs),
            "reproducible_cases": reproducible, "failures": failures,
            "tradeoffs": tradeoffs, "pairs": pairs,
            "note": "Advisory; source authenticity and semantic coverage require separate audits."}
