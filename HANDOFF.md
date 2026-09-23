# Project Handoff

Supplementary conversation cursor. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- Public release: **v0.3.0**
- Release tag: `8bf51d5b552587dd4d7a5d8ce87a48f89c3136de`
- Stage 4 human QA: PASS
- Final release workflow: PASS
- v0.3 trackers: closed
- v0.3 staged/research Draft PRs: merged where appropriate or closed as historical records
- No active v0.3 blocker.

## Release artifact

`Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip`

SHA-256:
`fbd73f1a477a1b64f19f0b4f25c31c805dc4f3e710a7f9f8ab3bea3d6fa4c03a`

Release:
`https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0`

## Important completed decisions

- UI -> `SelectorApplication` -> feature-backend architecture remains the product boundary.
- Non-fatal automated fixes should be batched for human QA checkpoints.
- Duplicate Review, Composite Split, Auto Crop, Source Organizer and Text Cleanup are independent product features/boundaries.
- Text detection + repair remain one Text Cleanup product module.
- Auto Crop uses conservative ISNetIS proposals, metadata decisions and human-authoritative ROI review.
- Source Organizer is the only optional workflow intended to reorganize active source file locations; it must remain transactional and explicit.
- permanent Qt i18n is in place; Chinese is source/default locale and English is live-switchable.
- PySide6-Essentials is retained; do not add PySide6-Addons without a new justified decision.

## Next action

There is no pending v0.3 action.

For new development:
1. start from current `main`;
2. open a new issue with explicit scope;
3. identify whether it is a hotfix, v0.3.x maintenance, or a new release line;
4. reuse the existing architecture / OpenSpec / batched-QA conventions;
5. do not reopen historical v0.3 branches merely because they still exist.

## Relevant references

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- `CHANGELOG.md`
- `RELEASE_NOTES_v0.3.0.md`
- tag `v0.3.0`
