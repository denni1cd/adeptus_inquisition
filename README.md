# Adeptus Inquisition

A standalone, event-triggered ChatGPT Work skill for failure recovery and evidence-based improvement of reusable Adeptus workflows. It does not replace Work coordination, Strategerium's Rules Lawyer, Necroneerium's Shade, or Factorium's specialist factories.

- Skill entrypoint: skills/adeptus-inquisition/SKILL.md
- Deterministic ledger and CLI: inquisition/engine.py and inquisition/cli.py
- Event and delegated-review schemas: schemas/
- Reproducible clean, failed, improved and regressed examples: fixtures/
- Local/CI executable tests: tests/
- Integration and candid runtime caveats: docs/

## Local standalone smoke tests

    python3 -m unittest discover -s tests -v
    python3 -m inquisition.cli --home .adeptus_inquisition ingest --package fixtures/milestone.json
    python3 -m inquisition.cli --home .adeptus_inquisition milestone --event-id evt-clean --inspection fixtures/clean_inspection.json
    python3 -m inquisition.cli --home .adeptus_inquisition show

Python 3.10 or later, standard library only.

## Use in ChatGPT Work

Install the directory skills/adeptus-inquisition/ using your Work environment's skill-import method from a pinned checkout. Verify the skill appears in a fresh Work invocation; repository presence alone does NOT install or activate it. Provide an authorized event JSON with complete evidence, and explicitly invoke adeptus-inquisition. See docs/OPERATIONS.md.

### What remains unverified
The offline gate tests execute real Python behavior and retry/version decisions, but **do not create real native Work subagents**. A Work-native delegation/audit bridge and fresh-agent skill loader probe must be validated in a separate actual Work run. Until then, required independent-agent acceptance is BLOCKED and the skill is not production-ready for autonomous adoption. Signatures from a unit test are not evidence of independent agents.

No other Adeptus repository was modified.
