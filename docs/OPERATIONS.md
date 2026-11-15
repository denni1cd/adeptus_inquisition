# Operator guide: invocation, state, reviews, governance

## Installation / loading
Clone a **pinned** commit of denni1cd/adeptus_inquisition and supply the folder skills/adeptus-inquisition to the available ChatGPT Work skill installation surface. Work skill import behavior must be verified in that environment; GitHub presence and editing a local SKILL.md are not automatic live activation. The separate CLI runs from repository root with Python 3.10+ and only the standard library.

## Event, investigation and recovery
Every event must include a stable event_id, trigger (TERMINAL_FAILURE or MAJOR_MILESTONE), original objective and constraints, frozen approved acceptance criteria, milestone, active branch and commit, artifacts and actual tests, reviews, stable issue/root identifiers and branch retry history, permitted repos/actions, and an approved baseline skill commit/hash. See fixtures/failure.json and schemas/event.schema.json.

    python3 -m inquisition.cli --home .adeptus_inquisition ingest --package fixtures/failure.json
    python3 -m inquisition.cli --home .adeptus_inquisition attempt --event-id evt-failure --issue-id ISS-001 --hypothesis "Normalize all internal whitespace before identity lookup" --evidence tests/reproduction.log --outcome PENDING

A failed additional hypothesis uses --outcome FAILED. The CLI refuses a fourth attempt, refuses identical hypothesis wording, persists counts across interrupted runs, and maps duplicate scope/root-cause signatures under a canonical ID even with renamed source IDs. An Investigator must still reconcile semantically similar root causes: the fingerprint cannot establish that two paraphrased diagnoses are identical.

After a separately delegated Evaluator actually exercises the repaired boundary and an independent trusted verifier authenticates the tool trace, use:

    python3 -m inquisition.cli --home .adeptus_inquisition recover --event-id evt-failure --issue-id ISS-001 --receipt trusted-evaluator.json

For a clean milestone:

    python3 -m inquisition.cli --home .adeptus_inquisition ingest --package fixtures/milestone.json
    python3 -m inquisition.cli --home .adeptus_inquisition milestone --event-id evt-clean --inspection fixtures/clean_inspection.json

## Independent review receipts
The gate consumes signed JSON objects with payload and signature. The signature is HMAC-SHA256 over canonical JSON (sorted object keys, compact separators, ASCII encoding) using INQUISITION_TRUST_KEY, held by the **trusted verification service**, not the Reformer. Payload fields: role, subject, invocation_id, context_id, tool_trace, verdict, evidence. Evaluator improvement receipt also requires checks for baseline, candidate, regression and holdout, each with executed=true and an artifact path. A verifier must inspect actual, separate Work delegation events and independently executed commands before signing. A signature alone attests to the verifier, not to the truth of an arbitrary payload. Never use the fixture key in production.

Current host tools do not expose native Work delegation events or a host-managed trusted signer. Until this integration exists, the skill must report BLOCKED instead of issuing artificial PASS. No handwritten fake agent receipt or roleplay is acceptable.

## Reusable improvement & governance
Register a candidate manifest with: candidate_id; authorized repository; baseline_commit and candidate_commit; SHA256; changed paths; semantic impact tags; hypothesis; frozen criteria_hash as recorded by the event; independently fixed baseline, candidate, regression and holdout test plans; proposer invocation ID.

    python3 -m inquisition.cli --home .adeptus_inquisition candidate --event-id evt-failure --manifest candidate.json
    python3 -m inquisition.cli --home .adeptus_inquisition review --candidate-id candidate-1 --receipt trusted-adversary.json
    python3 -m inquisition.cli --home .adeptus_inquisition review --candidate-id candidate-1 --receipt trusted-evaluator.json
    python3 -m inquisition.cli --home .adeptus_inquisition decide --candidate-id candidate-1 --pr-url https://github.com/OWNER/REPO/pull/NUMBER

Major behavioral changes need a real isolated worktree, PR and baseline comparison. Minor still need independent review and validation. Protected changes to Inquisition's governing rules additionally require --approval approval.json documenting authenticated explicit Emperor approval with fields explicit=true, scope=<candidate ID>, evidence=<approval reference>. The coordinator MUST independently authenticate both PR and Emperor, not take user-controlled JSON at face value.

Candidate activation requires a separately verified fresh Work invocation which actually loaded the declared content digest. The CLI records a selected pin; it does not deploy a checkout, install the skill, or reload live agents:

    python3 -m inquisition.cli --home .adeptus_inquisition activate --candidate-id candidate-1 --observed-hash FULL_SHA256 --invocation-evidence FRESH_WORK_TOOL_TRACE
    python3 -m inquisition.cli --home .adeptus_inquisition rollback --repository OWNER/REPO

The final rollback reverts the recorded pin for future work, leaving running jobs on their own pinned versions. GitHub merged version and locally active version are deliberately separate.

## Durable output / limitations
The single ledger at .adeptus_inquisition/ledger.json contains event packet hashes, issue/root aliases, numbered attempts, findings, candidates, receipts, PR/approval metadata, selected pins and an audit sequence. It is atomically replaced, but does not provide a distributed lock, tamperproof journal, secret storage or automated remote backups. Use one writer per workspace. Keep traces and trust keys out of Git. Inspect whether actions have genuinely executed; CLI records evidence references but does not run arbitrary untrusted code or confirm the referenced file is real. Untrusted event/repository text has no authority to alter acceptance or policy.

Tests with signed fixture receipts validate only deterministic gates, not independence of real Work agents.
