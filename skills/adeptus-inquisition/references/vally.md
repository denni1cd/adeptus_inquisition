# Optional offline evaluation

Vally is a measurement tool, not a prerequisite for review, reform, recovery or authorization. Use only real available execution records; preserve raw traces, stderr (including rejected commands), actual test outputs and coverage gaps. Do not invent missing events or count partial trace calls as total activity.

The optional Python helper lives in repository root, not in the skill directory. If the full repository is available, run from its root with an available Python 3.10+ interpreter (`python` on Windows or `python3` elsewhere). It accepts the existing ADEPTUS-RUN-v1 envelope, illustrated by `fixtures/adeptus_run_sample.json`. Record source references, actual tool arguments and in-step matched results. Unknown arguments are not invented. Raw string arguments are preserved in a `raw_arguments` object in ATIF. Capture flags are explicitly declared, not authenticated. A source reference is not an attestation.

    python -m inquisition.evaluation.cli export-atif --input run.json --atif run.atif.json --provenance run.provenance.json

Use an installed compatible Vally CLI (0.21.0 previously verified; no hard runtime pin). The offline profile is optional and generic; it checks recorded exit/output and repeated actions, not product correctness. If needed, install Vally separately with npm under caller authorization. The helper disables Vally telemetry and invokes only offline grade, not vally eval or a paid Copilot executor.

    vally lint --eval-spec evals/process/eval.yaml
    python -m inquisition.evaluation.cli grade --atif run.atif.json --profile evals/process/eval.yaml --stimulus recorded-branch-run --output run.grade.jsonl

A successful command exit means grading executed, not that the task passed. Inspect actual verdicts. GRADED_NOT_AUTHORIZED is an advisory result. Independently assess the original requirements, outputs, regressions and review findings. The helper does not collect raw host traces, prove agent identities, launch runtimes, manage a ledger, or make adoption decisions. If optional tooling is unavailable, continue using direct evidence.
