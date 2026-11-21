# Vally offline process evaluation — V1.1

## Purpose and boundaries

Inquisition's primary improvement objective is to inspect a real Strategerium,
Necroneerium, or Factorium execution, identify an evidenced process weakness,
develop a reversible process-level candidate, and demonstrate improved future
executions against frozen requirements. Its existing milestone/terminal-failure
triggers, three-attempt recovery rule, independent roles, major/minor/protected
governance, version pins and approval policy do **not** change here.

Vally is an **optional measurement backend**. It does not replace Investigator,
Reformer, Adversary, Evaluator, Shade, Rules Lawyer, or Emperor authorization.
It cannot certify real native Work subagent independence, issue signed receipts,
or hot-load a Work skill. Existing signed receipt gates remain BLOCKED until
a separate authenticated host integration is developed.

The V1.1 integration does **not** use Vally's Copilot SDK executor,
`vally eval`, LLM judges, or paid GitHub Copilot. It uses only **offline**
`vally grade` against previously recorded ATIF trajectories, with curated
deterministic grader profiles.

References:
- https://microsoft.github.io/vally/reference/cli/grade/
- https://microsoft.github.io/vally/reference/eval-spec/
- https://microsoft.github.io/vally/get-started/install/

## Installation

Python 3.10+ (stdlib) handles evidence and comparisons. For actual Vally grading,
install Node.js 22.15+ and the optional CLI:

```powershell
npm install --global @microsoft/vally-cli@0.21.0
vally --version
```

Vally collects pseudonymous CLI usage telemetry by default. To opt out:

```powershell
$env:VALLY_TELEMETRY_OPTOUT = "1"
```

No GitHub Copilot login or subscription is required for these **offline
deterministic** grading commands.

## 1. Collect real source evidence

The input envelope is `ADEPTUS-RUN-v1`, demonstrated in
`fixtures/adeptus_run_sample.json` (**synthetic sample only**).

Fields:
- `run_id`, `branch` (for example, `necroneerium`), `version` (pinned skill
  version), and `task` (objective and case identity).
- `events`: chronological structured records with `source` = `user`,
  `agent`, or `system`, a non-empty `message`, and a `source_ref`
  pointing to the original retrievable execution evidence.
- A tool-using agent event may contain `tool_calls` entries with
  `tool_call_id`, `function_name` and actual `arguments`. Its
  `tool_results` must match those call IDs **within that same step**.
- `capture`: declared coverage for `agent_steps`, `tool_results`,
  `subagent_events`, `timing`, `token_usage`. If missing, mark false.

Never infer tool calls, hidden subagent steps, or token counts from an agent
summary. A source reference is not automatically trusted. If real Work data
cannot be obtained, mark the evidence PARTIAL and do not calculate metrics
that depend on the missing portion.

There is **no automatic Work trace exporter** in V1.1; an authorized operator
or a future evidence bridge must populate this envelope from actual artifacts.
A copied narrative summary alone must not be characterized as a full trace.

## 2. Export to ATIF with provenance

From the Inquisition repository root:

```powershell
python -m inquisition.evaluation.cli export-atif `
  --input fixtures/adeptus_run_sample.json `
  --atif .local-evidence/sample.atif.json `
  --provenance .local-evidence/sample.provenance.json
```

This produces ATIF-v1.6 and a separate provenance manifest containing source
references, input/output hashes, and capture gaps. A missing event sequence
produces a **system-only** placeholder to satisfy ATIF's non-empty steps
requirement, never a fabricated agent action.

The adapter does not authenticate source references or delegate reviewers.
Keep private run evidence in a secure workspace, outside version control.

## 3. Grade a saved trajectory without Copilot

```powershell
vally lint --eval-spec evals/necroneerium/eval.yaml

python -m inquisition.evaluation.cli grade `
  --atif .local-evidence/sample.atif.json `
  --profile evals/necroneerium/eval.yaml `
  --stimulus recorded-branch-run `
  --output .local-evidence/sample.graded.jsonl
```

Choose the profile for the branch under review: `evals/necroneerium/`,
`evals/strategerium/`, or `evals/factorium/`.

The bundled YAML files are **starter deterministic smoke profiles**, not
comprehensive quality rubrics. Their paired `profile.json` files describe
meaningful quality and efficiency metrics that an actual test campaign must
measure using substantiated execution evidence. Tune the fixed graders
*before* comparing baseline/candidate, and preserve the same spec version
across both sides. Independent quality checks remain essential.

The bridge always invokes `vally grade`, never `vally eval`.
It deliberately rejects model-judge `prompt` / `panel`, executable
`program` graders, and dynamic executor settings. It accepts only the
curated simple YAML subset and calls Vally's own `lint` in CI. Supply only
reviewed local evaluation profiles, not arbitrary untrusted YAML.

**Important:** Vally `grade` exiting 0 means grading ran successfully.
A valid failed test can still exit 0. `GRADED_NOT_AUTHORIZED` never means
that independent review or approval succeeded.

If Vally isn't installed, investigation and the original Inquisition
procedures remain available; do not manufacture evaluation results.

## 4. Paired workflow comparisons

To demonstrate an improvement, actually execute a pinned **baseline**
and a pinned **candidate** on the same representative task set, including
at least one holdout not used to devise the change. Use fresh working
environments, unchanged acceptance criteria and independent review.

Normalize only observed evidence into
`INQUISITION-COMPARISON-v1` (see
`fixtures/paired_comparison_sample.json`, synthetic). Every case carries:
- `case_id`, `holdout`, `vally_grade_ref` pointing to a real graded output;
- referenced, independently checked `original_acceptance`,
  `regressions_clear`, and `independent_review` verdicts;
- referenced numerical metrics with `complete:true`;
- baseline/candidate commits and a frozen `criteria_hash` at plan level.

This normalization is currently **operator/reviewer-assisted**, not an
automatic proof that the Vally output authenticated these metrics.

```powershell
python -m inquisition.evaluation.cli compare `
  --input fixtures/paired_comparison_sample.json `
  --output .local-evidence/comparison.json
```

Results may be `REJECT_CANDIDATE`,
`NO_IMPROVEMENT_DEMONSTRATED`, `TRADEOFF_REQUIRES_REVIEW`,
or `SUPPORTED_FOR_INDEPENDENT_REVIEW`.

The comparison blocks missing/partial metrics, mismatched task cases, changed
holdout designations and unreferenced mandatory checks. Candidate quality
regressions are rejected before efficiency gains are considered. **All
comparison outputs set `approval:false`.** A comparison can support a
recommendation but never activate a skill by itself.

## 5. Attach results to the existing Inquisition ledger

After ingesting an authorized event in a durable state directory, attach
the actual provenance, grade output and comparison result:

```powershell
python -m inquisition.evaluation.cli attach `
  --home .adeptus_inquisition `
  --event-id YOUR_EVENT_ID `
  --provenance .local-evidence/sample.provenance.json `
  --grade .local-evidence/sample.graded.jsonl `
  --comparison .local-evidence/comparison.json
```

This records a `PROCESS_EVALUATION` finding, storing paths, SHA-256 hashes,
reported coverage and the advisory disposition. It does **not** mark
`RECOVERED`, `IMPROVEMENT_VALIDATED`, or grant any authorization.
The underlying event must still be PAUSED; all original governance checks
remain applicable.

## Acceptance status

- **PASS:** Vally 0.21.0 installed in GitHub Actions, real `vally lint` of
  three curated profiles, real `vally grade` on a **synthetic** ATIF fixture;
  standalone Python adapter, comparison and ledger-attachment tests.
- **NOT YET PROVEN:** Import of an authentic complete Work trace, process
  improvement of a live Adeptus branch, independent reviewer invocation
  authentication, and native candidate skill activation/rollback.
- **NEXT EXPERIMENT:** Supply one prior real Necroneerium run, preserve trace
  and coverage boundaries, pick a justified process weakness, run old/new
  Necroneerium skill versions against matched tasks and holdouts, and have
  genuine independent Work reviewers challenge the evidence.

Vally supports offline measurement. It is not a substitute for observing
whether future Adeptus executions actually improve.

## V1.2 scoped comparisons and trace diagnostics
The original compare command remains a legacy advisory pilot analysis, not a formal improvement gate. Use compare-scoped and the audit campaign in docs/SCOPE_AUDITS.md for actual adoption recommendations. The bundled profiles now include bounded repeated-action diagnostics; they are not quality rubrics. Treat their results as observed-trace signals only, especially if capture is PARTIAL. Vally threshold graders are NOT a proxy for correctness or independent boundary testing. Configure thresholds before a paired trial and audit their relevance; never optimize arbitrary command counts at the expense of correctness. The audit plan determines usable, independently supported quality and efficiency metrics. A missing metric remains unknown. The official grader documentation is https://microsoft.github.io/vally/reference/graders/max-repeat/.
