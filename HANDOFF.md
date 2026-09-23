# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- Integrated v0.3 merge: `521ac77f22996e2f160964da7c9b96f15ad29eaa`
- Stage 4 human QA: PASS
- Issue #17: CLOSED
- Current phase: **v0.3.0 release closeout**

## Release engineering

A release commit named `release: v0.3.0` is used as the final release gate.

The Windows build workflow:
- builds the complete Portable;
- runs source + packaged EXE self-tests;
- generates ZIP + SHA-256;
- on a `release: vX.Y.Z` main commit or `v*` tag, creates/updates the corresponding GitHub Release;
- reads `RELEASE_NOTES_<tag>.md` when present, otherwise falls back to `CHANGELOG.md`.

## Human QA evidence

Pinned candidate:
- code: `46bc803b8a806d9c1cf61ab9a6534241ac0cff8e`
- run: `35916370063`
- artifact ID: `10774289944`
- digest: `sha256:71835391390bcbe41199776565fbfecc9fc8d480af1f3dc4b60a9ca873c1c937`

User completed the consolidated Stage 4 checklist without reported failures. No product-code change followed the checkpoint.

## Immediate next action

1. Let the `release: v0.3.0` main workflows finish.
2. Require Architecture Boundaries + Windows Portable/package self-test PASS.
3. Verify GitHub Release v0.3.0 and attached ZIP/SHA-256.
4. Close completed production trackers and superseded old Draft PRs.
5. Close overarching v0.3 tracker.

Do not run another full human QA unless product behavior changes.
