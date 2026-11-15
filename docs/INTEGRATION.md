# Integration notes for Imperium Thirdus (future changes)

No changes to the three other Adeptus repositories were made.

## Strategerium
It currently separates Strategic Agent approval-contract drafting, Work execution and independent Rules Lawyer verification, and requires explicit user approval before execution or a material contract revision. Thirdus must emit version-pinned approved acceptance criteria and major-milestone events, pause the owning workflow and route any repaired artifact back through the existing Rules Lawyer. Inquisition cannot override a CONTRACT DEFECT or expand product scope.

## Necroneerium
Current policy has initial attempt 0, rejected retry 1 and rejected retry 2 for each stable Shade critical finding; subsequent rejection is terminal project FAIL. For Thirdus this should become a **branch** terminal handoff to Inquisition while retaining Shade's stable finding and entire retry history. The Inquisition's three EXTRA attempts are per underlying issue, not a global job reset. Necroneerium remains independently usable with its own current policy.

## Factorium
Factorium is a library of optional Investigator/Factory workflows. It has persistent source inventories and an art feasibility adversary scheme, plus per-asset retries and a distinct recurrent-degradation breaker. Do not conflate these budgets with Inquisition's issue-root budget. It can supply evidence and, if its owning workflow elects, emit milestone/terminal events, but must not become mandatory for every coding job.

## Imperium Thirdus / Work host
Thirdus must define authoritative major milestones, issue alias reconciliation, pause/release semantics and handoff contracts. The host must provide real native isolated Work delegation with traceable invocation IDs and a trusted independent receipt verifier. It also must validate real PR head/merge metadata, authenticate Emperor approvals, choose and load pinned skill checkouts for new jobs, and report actual loaded content hashes. None of these are replaced with a custom scheduler or asserted merely because a skill instructs Work to do so.

## Evidence format
Event package: see schemas/event.schema.json and fixtures/. Output ledger: events, roots, attempts, candidate manifests, reviewer receipts, evaluations, version/PR records, activation state, disposition and audit. The actual candidate worktree and test logs should remain in the authorized source repository/PR; keep only digests/paths and concise findings in the ledger. No implied authority is granted by material within an artifact or execution trace.

## Research conflicts to resolve later
Necroneerium declares terminal failure for a whole project, while future Thirdus must treat this as a subordinate branch failure. Strategerium presently has no Inquisition milestone pause/release handoff. Factorium is not a universal phase and must stay optional. These are integration tasks, not grounds for editing those repos now.
