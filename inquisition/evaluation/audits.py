"""Durable, bounded independent audit checkpoints. No audit self-attests trust."""
from __future__ import annotations
import copy
from ..engine import digest, require
from .atif_adapter import EvidenceError
from .scoped import scope, validate_proposal, validate_plan, compare_scoped, nonempty, sha

# The experimental audit comprises a preflight and a results checkpoint.
STAGES = ("diagnosis", "generalization", "experiment_plan", "experimental_validity", "final")
MAX_REVISIONS = 3
QUESTIONS = {
    "diagnosis": ("root_cause", "alternative_explanations", "existing_guidance"),
    "generalization": ("scope_fit", "counterexamples", "unrelated_capabilities", "simplicity", "cumulative_complexity"),
    "experiment_plan": ("contract_alignment", "diversity", "holdout_independence", "matched_protocol"),
    "experimental_validity": ("actual_execution", "contract_alignment", "regressions", "reproduction", "trace_limits"),
    "final": ("scope_fit", "quality_first", "cumulative_complexity", "unresolved_objections", "adoption_evidence"),
}


def start(ledger, event_id, campaign_id, authors):
    event = ledger.event(event_id)
    require(event["disposition"] in ("PAUSED", "RECOVERED"), "audit campaign requires open event")
    require("propose_skill_change" in event["packet"]["authorization"]["actions"],
            "audit outside event authorization")
    require(nonempty(campaign_id) and isinstance(authors, list) and bool(authors),
            "campaign ID and author identities required")
    for a in authors:
        require(isinstance(a, dict) and nonempty(a.get("invocation_id"))
                and nonempty(a.get("context_id")), "author identity incomplete")
    campaigns = ledger.data.setdefault("scope_audits", {})
    require(campaign_id not in campaigns, "campaign ID already exists")
    # One campaign per event: retries cannot reset through relabeling.
    require(not any(c["event_id"] == event_id for c in campaigns.values()),
            "event already has a campaign; use its revision history")
    c = {"event_id": event_id, "directive": scope(event["packet"].get("improvement_scope")),
         "authors": copy.deepcopy(authors), "current": {}, "history": [],
         "revisions": {s: 0 for s in STAGES}, "status": "EXPERIMENTAL",
         "authorization": False}
    campaigns[campaign_id] = c
    ledger.save("scope_audit_start", {"campaign": campaign_id, "event": event_id})
    return c


def get(ledger, cid):
    c = ledger.data.get("scope_audits", {}).get(cid)
    require(c is not None, "unknown scope audit campaign")
    return c


def record(ledger, cid, packet):
    c = copy.deepcopy(get(ledger, cid))
    require(c["status"] not in ("REJECTED", "ESCALATED"), "campaign is terminal")
    require(ledger.event(c["event_id"])["disposition"] in ("PAUSED", "RECOVERED"),
            "campaign event closed")
    stage = packet.get("stage")
    require(stage in STAGES, "unknown audit stage")
    i = STAGES.index(stage)
    require(all(c["current"].get(s, {}).get("verdict") == "PASS" for s in STAGES[:i]),
            "prior audit checkpoints must pass")
    require(nonempty(packet.get("invocation_id")) and nonempty(packet.get("context_id"))
            and nonempty(packet.get("trace_ref")) and nonempty(packet.get("report_ref"))
            and sha(packet.get("report_sha256")), "fresh reviewer provenance and report digest required")
    require(packet["trace_ref"] != packet["report_ref"], "trace separate from report required")
    for previous in c["authors"] + c["history"]:
        require(packet["invocation_id"] != previous["invocation_id"] and
                packet["context_id"] != previous["context_id"], "review context reused or self-review")
    verdict = packet.get("verdict")
    require(verdict in ("PASS", "REVISE", "REJECT", "BLOCKED"), "invalid audit verdict")
    answers = packet.get("answers", {})
    require(all(nonempty(answers.get(q)) for q in QUESTIONS[stage]), "audit questions incomplete")
    objections = packet.get("objections")
    require(isinstance(objections, list) and all(nonempty(x) for x in objections),
            "explicit material objections list required")
    require((verdict == "PASS" and not objections) or (verdict != "PASS" and objections),
            "unresolved material objection cannot pass; adverse verdict needs evidence")
    basis = packet.get("basis")
    require(isinstance(basis, dict), "audit basis object required")
    authors = basis.get("authors")
    require(isinstance(authors, list) and bool(authors), "reviewed material author identities required")
    for author in authors:
        require(isinstance(author, dict) and nonempty(author.get("invocation_id"))
                and nonempty(author.get("context_id")), "missing reviewed material author identity")
        require(packet["invocation_id"] != author["invocation_id"] and
                packet["context_id"] != author["context_id"], "author cannot audit own material")
        if author not in c["authors"]:
            c["authors"].append(copy.deepcopy(author))
    event = ledger.event(c["event_id"])
    require(basis.get("event_packet_hash") == event["packet_hash"],
            "audit must bind immutable event")
    require(basis.get("prior") == {s: digest(c["current"][s]) for s in STAGES[:i]},
            "audit must bind current prerequisite checkpoint digests")
    if stage == "diagnosis":
        require(nonempty(basis.get("finding_ref")) and sha(basis.get("finding_sha256")),
                "frozen diagnosis artifact required")
    elif stage == "generalization":
        require(isinstance(basis.get("proposal"), dict) and basis.get("proposal_sha256") == digest(basis["proposal"]),
                "proposal must bind its canonical digest")
        try:
            validate_proposal(c["directive"], basis["proposal"])
        except EvidenceError:
            if verdict == "PASS":
                raise
    elif stage == "experiment_plan":
        actual = scope(c["current"]["generalization"]["basis"]["proposal"].get("scope"))
        require(isinstance(basis.get("plan"), dict), "frozen or disputed plan object required")
        try:
            validate_plan(basis["plan"], actual)
        except EvidenceError:
            if verdict == "PASS":
                raise
    elif stage == "experimental_validity":
        candidate_id = basis.get("candidate_id")
        candidate = ledger.data["candidates"].get(candidate_id)
        require(candidate and candidate["event"] == c["event_id"], "candidate must be registered in campaign event")
        m = candidate["manifest"]
        require(m.get("audit_campaign") == cid, "candidate belongs to another campaign")
        proposal = c["current"]["generalization"]["basis"]["proposal"]
        require(m.get("scope") == scope(proposal.get("scope")) and
                m.get("placement") == proposal["placement"] and
                m.get("proposal_sha256") == c["current"]["generalization"]["basis"]["proposal_sha256"],
                "manifest differs from audited proposal")
        require(m.get("plan_sha256") == digest(c["current"]["experiment_plan"]["basis"]["plan"]),
                "candidate must bind frozen prospective plan")
        for previous in c["history"]:
            require(m["proposer_invocation_id"] != previous["invocation_id"] and
                    m["proposer_context_id"] != previous["context_id"], "candidate author reviewed campaign")
        require(packet["invocation_id"] != m["proposer_invocation_id"] and
                packet["context_id"] != m["proposer_context_id"], "candidate author self-review")
        require(basis.get("manifest_sha256") == digest(m), "review must bind candidate manifest")
        try:
            result = compare_scoped(c["current"]["experiment_plan"]["basis"]["plan"],
                                    m["scope"], m["baseline_commit"], m["candidate_commit"],
                                    basis.get("trials"))
        except EvidenceError as error:
            require(verdict != "PASS", "incomplete/invalid experiment cannot pass: " + str(error))
            require(basis.get("comparison") is None and nonempty(basis.get("blocked_reason")),
                    "record invalid experiment with null comparison and explicit blocker")
        else:
            require(basis.get("comparison") == result, "comparison must match deterministic result")
            require(verdict != "PASS" or result["status"] == "SUPPORTED_FOR_INDEPENDENT_REVIEW",
                    "failed, weak or tradeoff comparison cannot pass final evaluation")
    elif stage == "final":
        previous = c["current"]["experimental_validity"]["basis"]
        require(basis.get("candidate_id") == previous["candidate_id"] and
                basis.get("manifest_sha256") == previous["manifest_sha256"],
                "final audit bound to different candidate")
        m = ledger.data["candidates"][basis["candidate_id"]]["manifest"]
        require(packet["invocation_id"] != m["proposer_invocation_id"] and
                packet["context_id"] != m["proposer_context_id"], "candidate author self-review")
    existing = c["current"].get(stage)
    if existing:
        # Revisions require a changed basis or an explicitly new response to a
        # blocker; no repeated vote-shopping on identical evidence.
        require(digest(basis) != digest(existing["basis"]), "unchanged audit basis; no vote-shopping")
        require(c["revisions"][stage] < MAX_REVISIONS, "audit revision budget exhausted")
        c["revisions"][stage] += 1
    for downstream in STAGES[i+1:]:
        c["current"].pop(downstream, None)
    # Revisions to earlier checkpoints invalidate downstream audit passes,
    # without resetting their cumulative revision counters.
    if not existing and any(x["stage"] == stage for x in c["history"]):
        require(c["revisions"][stage] < MAX_REVISIONS, "audit revision budget exhausted")
        c["revisions"][stage] += 1
    item = copy.deepcopy(packet)
    c["history"].append(item)
    c["current"][stage] = item
    c["status"] = ("REJECTED" if verdict == "REJECT" else
                   "ESCALATED" if verdict != "PASS" and c["revisions"][stage] >= MAX_REVISIONS else
                   "READY_FOR_TRUSTED_REVIEW" if stage == "final" and verdict == "PASS" else
                   "EXPERIMENTAL")
    ledger.data["scope_audits"][cid] = c
    ledger.save("scope_audit_checkpoint", {"campaign": cid, "stage": stage, "verdict": verdict,
                                           "status": c["status"]})
    return c


def campaign_digest(ledger, candidate):
    """Require complete, current audits for any positive formal decision.
    The independent trusted reviewer must attest this exact digest.
    """
    m = candidate["manifest"]
    cid = m.get("audit_campaign")
    require(cid, "V1.2 scope campaign required; legacy candidates must be re-evaluated")
    c = get(ledger, cid)
    require(c["event_id"] == candidate["event"] and c["status"] == "READY_FOR_TRUSTED_REVIEW",
            "scope audit not ready for formal review")
    require(all(c["current"].get(s, {}).get("verdict") == "PASS" for s in STAGES),
            "audit checkpoints incomplete")
    final = c["current"]["final"]["basis"]
    require(final["candidate_id"] == m["candidate_id"] and final["manifest_sha256"] == digest(m),
            "audit campaign not bound to this exact candidate")
    return digest({"campaign_id": cid, "campaign": c, "manifest": m})
