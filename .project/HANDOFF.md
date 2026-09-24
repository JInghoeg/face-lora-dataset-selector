# Project Handoff

Supplementary conversation cursor. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Current state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- v0.3.0 public release: **WITHDRAWN**
- Reason: user reported multiple bugs; full manual QA had not actually been completed.
- Stage 4 QA: **REOPENED / NOT PASSED**
- v0.3 umbrella and feature trackers: reopened.
- Current phase: **bug reproduction + manual QA recovery**

## Critical correction

The prior assistant incorrectly interpreted the user's “完成了” as “manual QA passed” and then:
- marked Issue #17 complete;
- merged the staged v0.3 stack to main;
- created v0.3.0;
- closed v0.3 trackers.

The merge to `main` is kept as development state, but the release acceptance was invalid. The Release/tag are being deleted and the trackers have been reopened.

## Next action

1. Ask the user for the concrete bugs they found, ideally screenshots + reproduction steps.
2. Reproduce/fix them one by one without declaring release readiness.
3. Build a new unified QA Portable after fixes.
4. Give the user one explicit manual QA checklist.
5. Do **not** publish until the user explicitly says the manual QA passed.

## Non-negotiable release rule

CI green, self-test green, and packaged Portable smoke are not human QA.

Only an explicit user statement that the manual QA passed can close Stage 4 and authorize release.
