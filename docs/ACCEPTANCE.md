# V1 acceptance execution ledger — 2026-11-15

Evidence: GitHub Actions run https://github.com/denni1cd/adeptus_inquisition/actions/runs/43731007013 at commit 66463728d65392da78905acc12b0e0f66bf90cb9 executed 12 Python unittest checks successfully, plus an actual detached baseline/candidate worktree selection and skill-file SHA256 check. PR https://github.com/denni1cd/adeptus_inquisition/pull/1 is real, open, draft. The test run's log printed candidate SKILL.md SHA256 1cababc7b1f04395671cf973f71bf7edfce10113e416fe7eff0eaebf750c1268. CI may rerun as the PR evolves.

**Crucial scope note:** A synthetic HMAC-signed unit-test receipt is NOT an actual native ChatGPT Work subagent invocation. "PASS" below means the full requested scenario was actually exercised; when that did not happen, the top-level status is BLOCKED regardless of green unit tests.

| Requested acceptance test | Result | Executed evidence | What is still needed |
| --- | --- | --- | --- |
| 1. Successful milestone without unnecessary change | PASS (standalone ledger and actual fixture) | test_1_clean_milestone_released_without_change; milestone package and persisted NO_CHANGE_JUSTIFIED; candidate registry empty | A live Work milestone handoff remains an integration task |
| 2. Recoverable execution failure with independent verification | BLOCKED | Real fixture baseline fails and corrected normalization passes; test_2 verifies pending repair refuses missing verifier key; a **synthetic** signed receipt can move deterministic state to RECOVERED | Native separate Work Reformer/Evaluator with authenticated trace and direct boundary verification |
| 3. Genuine reusable improvement | BLOCKED | Baseline reusable_v0 fails whitespace equivalence; reusable_v1 and the actual engine.normalize pass ordinary, regression and unseen tab/newline cases; test_3 runs comparison-decision gate using **synthetic** receipts | Native adversarial challenge plus independently executed baseline/holdout tests under a genuine Work candidate lifecycle |
| 4. Bad improvement introduces regression | BLOCKED | reusable_bad incorrectly aliases all inputs, and test_bad_candidate_regresses_other_issue exposes it; test_4 rejects a candidate with synthetic FAIL review/evaluator receipts | Observe genuine independent review or evaluator find and reject regression |
| 5. Exhausted recovery and stable issue ID | BLOCKED for full recovery; PASS for enforced budget | test_5 writes exactly three distinct hypothesis entries, persists ESCALATED, rejects fourth attempt and survives source issue renaming across event IDs | Actual three tested fixes and genuine failure evidence; current fixture attempts are simulated events, not three executed repair attempts |
| 6. GitHub governance / provisional version / rollback | BLOCKED for actual Work activation; PASS for Git mechanics | GitHub PR #1 created; CI checked separate detached main baseline and unmerged feature worktrees, and computed candidate SKILL.md hash. test_6 verifies MAJOR PR requirement, signed-loader precondition, distinct selected pin and rollback | Work loader that genuinely executes pinned unmerged skill in a fresh subagent, and trusted load receipt; this PR remains draft |
| 7. Genuine independent-agent enforcement | BLOCKED | test_7 blocks missing, unsigned and same-context reviews; HMAC-signed synthetic contexts also demonstrate policy test limits | A trusted Work-native delegation-log verifier that cannot be impersonated by the Reformer, and two observed independent agent invocations |
| 8. Protected governance modification | PASS (unauthorized activation blocked) | test_8 attempts changing inquisition/engine.py, classifies PROTECTED and denies validation without trusted Emperor approval | Positive authorized activation remains unverified and should not be inferred |

## Additional negative gates
- Immutable event payload rejects same-ID modification; criteria-hash tampering rejected.
- Candidate must be confined to authorized repo and permitted actions.
- Recovery gate cannot accept unsigned evaluation when trusted key is unavailable.
- Per-root history survives new Ledger instance and reconciles equal normalized causes across event IDs.
- Major/PROTECTED classification depends on semantic tags and sensitive paths, not diff line counts.
- Evidence paths are recorded; the deterministic engine does not automatically execute provided commands or prove that all paths exist.

## Non-goals and follow-up
This skill is independently invocable as an instruction package plus CLI and fixtures, but full autonomous self-improvement is NOT yet proven. A Work session with native agent delegation, host-attested review receipts and fresh-skill loading is required. Work should invoke the skill in this PR's pinned checkout, run tests 2–4 and 7 against real delegated contexts, demonstrate the exact loaded hash for test 6, and update this table with links to authentic tool traces. Never convert these BLOCKED entries to PASS based on a simulated agent or a written scenario.
