# Adeptus Inquisition — v1.0.0

**First stable release: v1.0.0.** The earlier “V2” label refers to the development iteration tested before this first release, not a previously shipped stable version.

Independent process improvement and failure recovery. No external orchestrator knowledge is required.

Install or update the skill at `skills/adeptus-inquisition/` under the existing skill name. A complete clone is optional if you want the Vally utilities. Read [SKILL.md](skills/adeptus-inquisition/SKILL.md).

## Usage

- Review a completed execution and recommend improvements, without changing the process.
- Review and reform a process: independently audit the recommendation, implement and independently check the process update, and publish or stage it only within authorization. The caller owns subsequent runs and effectiveness measurement.
- Reform a previously reviewed recommendation.
- Investigate and recover a specified failure.

The caller determines when to invoke Inquisition and what authority it has. Inquisition never re-executes the modified skill or delegates live baseline/candidate workflow tests; it hands recommended operational checks back to the invoker. Recovery may directly reproduce and test the assigned failure without rerunning the originating skill's workflow. The skill uses existing runtime tools and separate reviewer contexts, and maintains a simple case record. General improvement is the default; domain and task scopes are supported.

## Rebuild boundary

V2 replaces the V1.2 mandatory event/ledger and receipt state machine with an instruction-led sequential workflow. No required trigger, orchestration integration, fixed runtime version, nested CLI launcher, fixed trial count, or signing service. Independent audits, proportionate implementation checks, downstream regression/transfer test recommendations, three-attempt recovery and audit correction limits, protected approvals, repository authority and rollback remain.

Old V1.2 source, records and active pins are not migrated or deleted by this repository change. Preserve prior backups and case histories at installation; consult previous recovery attempts rather than resetting them. Restore the prior installation to roll back. V1.2's exact Git revision is `723af2886409e0a4f84c47a3247476727cf7f059`. Do not copy obsolete instructions into the active skill. No other skill is changed.

[Operational acceptance](docs/ACCEPTANCE.md) describes focused tests. [Optional Vally](skills/adeptus-inquisition/references/vally.md) can grade saved traces without a paid Copilot dependency.
