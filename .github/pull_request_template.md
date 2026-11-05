## Summary

What does this PR change and why?

## Scope

Affected modules:
- [ ] ranking
- [ ] duplicates
- [ ] composite
- [ ] text cleanup
- [ ] auto crop
- [ ] organizer/export
- [ ] application/core/infrastructure
- [ ] UI only
- [ ] build / CI / repository process
- [ ] docs / repo hygiene

## Behavior / data risk

- User-visible behavior changed: YES / NO
- Source file mutation risk: NONE / LOW / HIGH
- Persistence/cache/schema risk: NONE / LOW / HIGH
- Startup/Portable risk: NONE / LOW / HIGH

## Architecture checklist

- [ ] Optional feature code does not import sibling feature internals.
- [ ] New UI code uses the application boundary rather than direct filesystem/model/cache calls.
- [ ] Generic infrastructure contains no feature-specific product policy.
- [ ] Local changes stay incremental when the changed set is known.
- [ ] Architecture docs/ADR updated if dependency direction changed.

## Validation

Automated:
- [ ] self-test / relevant unit coverage
- [ ] architecture CI
- [ ] runtime CI
- [ ] Portable smoke when required

Human QA — select exactly one:
- [ ] HUMAN PASS
- [ ] HUMAN UNVERIFIED
- [ ] HUMAN NOT REQUIRED
- [ ] IMMEDIATE HUMAN QA REQUIRED

Human test delivery (required when requesting workstation QA; mark N/A only if genuinely no human workstation test is needed):
- [ ] N/A — no workstation test requested by this PR
- [ ] Exact CI-verified artifact/run and one-command setup+launch+report delivery are provided
- [ ] Cached runtime/model reuse or incremental overlay; G: workspace and safe cleanup verified
- [ ] No manual Actions download, ZIP extraction, model copy, dependency install or log hunting
- [ ] Any remaining HUMAN UNVERIFIED target gate is explicit

QA debt issue:
State impact rationale:

## Project continuity

State impact — select exactly one:
- [ ] Yes — `docs/PROJECT_STATE.md` updated to the expected post-merge state
- [ ] No — canonical current state is unchanged

Plan impact — select exactly one:
- [ ] No accepted-plan change
- [ ] Adds/changes accepted future direction
- [ ] Supersedes/removes accepted future direction

Plan tracker:
Execution authorization note:

Decision impact:
- [ ] None
- [ ] Existing/new Decision Record linked or updated

## Release impact

- [ ] Not a release-preparation PR
- [ ] Release preparation — `.project/release_gate.json` matches the approved version and explicit HUMAN PASS

## GitHub sync

- [ ] Relevant Issue updated when applicable.
- [ ] Completing work uses `Closes #N` when appropriate.
- [ ] Accepted future directions are carried forward when a tracker/version is closed or superseded.
- [ ] Decisions/product semantics recorded before merge when applicable.
- [ ] Release notes/public version links updated when applicable.

For a genuinely language-specific README-only change, add `[readme-sync-exempt]` to the PR body and explain why.
