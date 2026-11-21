# Scope, generalization and independent audits (V1.2)

This is an extension of Inquisition, not a new orchestrator. Original milestone/terminal triggers, branch ownership, exceptional recovery budget, approval classes, PR policy, and rollback remain. Use the evaluated workflow's actual execution surface (Codex for Necroneerium, available Work runtime for Work skills). An experiment is not activation.

## 1. Directive and recommendation placement

The immutable event may omit `improvement_scope` (GENERAL), or explicitly include:

    {"kind":"GENERAL"}
    {"kind":"DOMAIN","target":"transactional/concurrent applications"}
    {"kind":"TASK","target":"repeatable Stockroom workflow"}

GENERAL covers the intended capability of the branch, not every imaginable task. A GENERAL investigation may find a narrower opportunity; explain it and propose conditional guidance. A restricted directive cannot be widened or redirected silently. Scope describes the *process change*, not a permission to modify the target product.

A proposal has `scope`, `placement` (core for GENERAL, conditional otherwise), `hypothesis`, `applicability`, `counterexample_analysis`, `complexity_analysis`, and `scope_rationale` if narrower than the directive. Conditional guidance must activate only when applicable. The implementation may be a short conditional instruction or separate opt-in guidance; do not build specialized modules unnecessarily. Test activation AND non-activation. The CLI records the scope of an adopted skill pin; it is not a runtime router.

Quality and existing capabilities take precedence over accuracy of efficiency metrics, speed, or token count. Review the entire accumulated skill at generalization and final recommendation. Seek conflicting or obsolete rules and recommend deletion/simplification when justified. At existing major milestones, consider a cumulative review when warranted; no new continuous trigger is introduced.

## 2. Work sequence

Use the installed skill and the existing ledger (single writer). In Windows PowerShell use a verified `python` executable, on Linux/macOS `python3`.

    python -m inquisition.cli --home EXPERIMENT_STATE ingest --package event.json
    python -m inquisition.cli --home EXPERIMENT_STATE audit-start --event-id EVENT --campaign-id AUDIT --authors authors.json

Authors is an array of actual invocation/context identity objects covering the Investigator and Reformer and any known authors of reviewed work. Do not make up identities. One campaign per event prevents resetting its revision counters under a new label. If multiple separate improvement hypotheses are warranted, submit distinct authorized events with their source evidence and stable identity; do not split/relabel an exhausted investigation to evade its budget.

Four mandatory independent audit checkpoints are implemented as five recorded stages:

| Stage | What an isolated auditor challenges |
| --- | --- |
| diagnosis | root cause; alternatives; whether existing guidance already solves it; source evidence and flawed acceptance tests |
| generalization | scope fit; concrete counterexamples; unrelated capabilities; simplicity; cumulative complexity |
| experiment_plan (preflight of experimental audit) | contract alignment; distinct tasks; independently selected holdouts; matched protocol |
| experimental_validity (post-run experimental audit) | actual runs and artifact inspection; contract alignment; regressions; reproducibility; trace gaps |
| final | scope fit; quality-first decision; cumulative complexity; unresolved objections; adoption evidence |

Auditors must genuinely use fresh contexts, be independent of the material's authors, and not receive private author reasoning. Use native delegation or proven separately launched agent executions; a role label, template report or guessed identifier is not proof. The Investigator designs a diagnosis; the Reformer proposes a change; the independent evaluator selects and freezes benchmarks; no author reviews its own work. Run checkpoints before proceeding, not after all work is done. A real audit should identify falsifiable counterexamples and independently inspect the underlying evidence.

Use:

    python -m inquisition.cli --home EXPERIMENT_STATE audit-record --campaign-id AUDIT --packet audit.json

Each packet is JSON and includes:
- `stage`, actual `invocation_id` and `context_id`, separate `trace_ref` and `report_ref`, actual lowercase hex `report_sha256`, `verdict` (PASS, REVISE, REJECT, BLOCKED).
- `answers`: a mapping from every stage-specific question in `inquisition/evaluation/audits.py:QUESTIONS` to a substantive evidence-based response; `objections`: explicit list of material unresolved objections (empty only for PASS).
- `basis`: `event_packet_hash` from ledger; `prior`: map of each preceding stage to canonical SHA-256 of its current packet (empty for diagnosis); authors (actual invocation/context identities of creators of the material being audited), and stage-specific fields below. The ledger stores the full packets, hashes, and decisions. Compute canonical digests with `inquisition.engine.digest`; use SHA-256 of actual bytes for file artifacts.

Stage basis fields:
- diagnosis: `finding_ref`, `finding_sha256`.
- generalization: `proposal` (object above), `proposal_sha256` (canonical digest of object).
- experiment_plan: `plan` (below). An adverse audit can persist a disputed plan without passing it.
- experimental_validity: `candidate_id`, `manifest_sha256` (canonical manifest digest), `trials`, `comparison` (exact result of compare-scoped). For an incomplete/invalid experiment, null comparison and explicit `blocked_reason`; cannot PASS.
- final: `candidate_id`, `manifest_sha256` bound to results checkpoint.

PASS cannot have unresolved material objections. REVISE routes to the responsible stage, then a fresh context audits materially changed evidence. Initial review plus at most three substantive revisions per checkpoint, including repeats caused by upstream changes. Later checkpoints are invalidated on upstream revision. REJECT or exhausted revision budget stops the campaign for Emperor review. Do not vote-shop with unchanged audit basis or merely rename a hypothesis. The CLI enforces record shape, declared ID separation, canonical bindings, revision counts and deterministic comparison; it cannot itself inspect hidden thoughts, establish true isolation or authenticate the artifact references. The external trusted review remains necessary for adoption. Use an actual changed artifact, not changing a reference string to simulate revision.

## 3. Freeze a diverse benchmark before candidate implementation

The plan object:
- `protocol_sha256` actual hash of independently frozen protocol; `selection_evidence` points to independently selected benchmark rationale; `repetitions` integer >=2 per case per arm.
- `cases`: list of objects with unique `case_id` (no colons), unique `task_sha256` (actual frozen task hash), `criteria_sha256` (actual acceptance contract hash), `family`, `category`, `in_scope` boolean and `hidden_from_reformer` boolean. Categories must cover origin, transfer, unrelated, holdout, established. An optional negative_control is allowed. GENERAL requires at least three genuinely different families and an unrelated family distinct from the origin. Scoped changes require origin, transfer and holdout in scope and unrelated/negative controls out of scope. Holdout metadata can be shared; private requirements, tests and solution traps are retained separately by evaluator until candidate freeze. Hashing different prompts does not prove meaningful diversity; audit semantics.
- `metrics`: each metric has `kind` quality or efficiency, `direction` lower or higher, `tolerance` nonnegative materiality threshold, fixed before testing. Set plan.primary_outcome to a named metric or a mandatory quality check representing the predicted benefit. Use direct quality measures; do not set thresholds to hide damage.

Use comparable pinned model, reasoning, task requirements, tool access, starting repo, budgets, environment and execution order; counterbalance order when practical. Verify exact acceptance harness requirements before any runs. If an assertion requires unspecified behavior, preserve the original result as invalid for adoption, independently reconcile the specification, refreeze a corrected protocol and rerun BOTH arms. Do not silently change the acceptance test or reuse one arm under new criteria.

Create the candidate in isolation after preflight. Register existing required manifest fields plus:
- `scope`, `placement` matching the audited proposal.
- `audit_campaign`, `proposal_sha256`, `plan_sha256` (canonical plan digest).
- exact candidate commit/content digest, unchanged baseline and original event criteria hash.

    python -m inquisition.cli --home EXPERIMENT_STATE candidate --event-id EVENT --manifest candidate.json

Perform actual matched runs. Preserve raw traces, applications, independent executable acceptance outcomes, and unsupported completion claims, not just agent-authored summaries. Every trial contains `case_id`, `arm` (baseline/candidate), `repetition`, exact `task_sha256`, `criteria_sha256`, pinned `commit`, `run_ref`, `run_sha256`, `environment_sha256` (same within pair). Mandatory `checks` keys original_acceptance, regressions_clear, independent_review, no_false_pass, no_capability_loss each have `passed` boolean and `evidence_ref`. All trial rows require actual independent `contract_alignment_verified` and `contract_alignment_ref`. For restricted scope include `conditional_guidance_applied` and `conditional_evidence_ref` (only candidate in-scope arms activate). Include `trace` with coverage PARTIAL / DECLARED_COMPLETE_NOT_AUTHENTICATED / UNAVAILABLE, evidence_ref and optional vally_grade_ref. Metrics have value, complete:true and evidence_ref; incomplete metrics are not zero. Vally remains optional. Use branch-appropriate independent outcomes (e.g. actual acceptance tests, Rules Lawyer contract evidence, independent art/dialogue quality review) and explicitly disclose unavailable measures.

Compare an object with plan, scope, baseline_commit, candidate_commit, trials:

    python -m inquisition.evaluation.cli compare-scoped --input comparison-input.json --output comparison.json

The result never grants approval. Every candidate trial must pass mandatory quality checks. Any material quality loss in even one unrelated case rejects; efficiency losses beyond declared tolerance require tradeoff review, not automatic adoption. The predeclared primary benefit must reproduce in every repetition of an origin case AND a distinct in-scope transfer or holdout case. GENERAL additionally requires that the two cases belong to different task families. Neutral unrelated cases alone do not establish general improvement. This conservative minimum is a structural safeguard, not a proof of statistical significance or generalization. An independently authored broader test suite can demand more. A pilot or one-task repeat can remain useful experimental evidence but cannot pass the scoped final gate. Review multiple metrics jointly; low command counts by themselves do not signify success. Use actual raw evidence for case classifications and tolerance rationale.

## 4. Trusted decision without mandatory HMAC

Experimentation needs no signature, Work-specific loader, or paid Copilot. The audit can record adverse results and make provisional recommendations with missing trust infrastructure. Never manufacture trusted receipts or close a valid experiment solely because a signer is unavailable.

After all audit stages PASS, compute the exact campaign binding:

    python -m inquisition.cli --home EXPERIMENT_STATE audit-digest --candidate-id CANDIDATE

For formal validation, the original independent Adversary and Evaluator trusted receipts must both include this exact `audit_digest`, with original evidence fields and applicable execution checks. Protected approval also includes explicit Emperor approval for that digest; loader receipt includes it plus actual loaded commit/content hash from a fresh invocation of the target runtime. Evidence must show distinct genuine contexts, real executions, review reports and effective scope, not merely the existence of files.

Two supported trust routes:
1. Existing HMAC-SHA256 receipt with a key held by a separate trusted verifier.
2. An independent operator (not the Investigator/Reformer or execution agents) inspects actual runtime provenance, audit history, artifacts, and exact receipt payloads, then pins their canonical payload SHA-256 digests to an external trust store. This route does not require any host signing service.

Example external store format (example digests are NOT valid approvals):

    {"schema":"INQUISITION-OPERATOR-PINS-v1","approved_payload_sha256":[]}

A trusted operator process sets `INQUISITION_OPERATOR_TRUST_STORE` to its independently provisioned file. Receipt JSON may contain only `payload` in this mode. Compute digest(payload) using the original canonical JSON algorithm and verify the exact inspected payload; the store must never be writable by experimental agents. Run formal `review`, `decide` and `activate` only under that separate trusted operator boundary. Do not set this variable or create pins from inside an untrusted agent session. An environment variable/file alone is not an identity provider; if agents can control it or the ledger or code, there is no verified trust boundary and formal approval remains BLOCKED. The ledger is still single-writer and not tamperproof. The system cannot automatically certify native Work/Codex independence or freshness merely because a report exists. This optional manual route deliberately avoids falsely assuming a host attestation API. Existing HMAC mode remains supported. No blanket overrides and no unsigned self-approval.

Original classification and authorization rules remain: MINOR within prior authorization, MAJOR needs actual PR and existing approved-baseline/pin rules, PROTECTED requires explicit Emperor approval. All positive decisions and activations require the complete current scoped audit binding. Legacy V1/V1.1 candidate records remain readable but may not be newly approved/activated until re-evaluated against V1.2. Previously active pins are not silently changed; existing rollback still works.

## 5. Acceptance and known limitations

Unit fixtures simulate policy inputs and receipts, not actual agents. CI performs real Vally offline grading on synthetic ATIF. No live Work/Codex install, automatically trusted signer, or empirical improvement to other Adeptus skills is proven here. The branch's default audit minimums and three revision budget are conservative implementation choices; evaluate their practical cost in the next real experiment. Do not change existing installed skills or publish a candidate automatically when testing V1.2.
