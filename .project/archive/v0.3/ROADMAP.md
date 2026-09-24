# v0.3 Roadmap

Status date: 2026-09-24

## Current status

**v0.3.0 RELEASE WITHDRAWN — HUMAN QA FAILED / INCOMPLETE**

A public v0.3.0 release was created prematurely after the user's message “完成了” was incorrectly interpreted as completion of the full manual QA checklist. The user later reported that the published build contains multiple bugs.

The release and tag are being removed. v0.3 is back in bug-fix + manual-QA stage.

## Implementation status

The integrated v0.3 feature stack remains on `main` for development:
- Dataset / View workflow
- Duplicate Review
- AI Review Bundle
- Composite Split
- General Auto Crop
- Source Organizer
- Text Cleanup boundary
- Fluent Filmstrip UI
- live zh_CN / en_US Qt i18n

## Release gates

- [x] v0.3 stack integrated to `main`
- [x] automated architecture and regression coverage
- [x] official Portable build pipeline
- [x] packaged EXE self-test
- [ ] reproduce all user-reported bugs
- [ ] fix confirmed release blockers / obvious workflow defects
- [ ] build a new pinned unified QA Portable
- [ ] run full real manual QA
- [ ] Source Organizer manually verified on a disposable/copy dataset
- [ ] user explicitly reports manual QA PASS
- [ ] final affected CI + Portable smoke PASS
- [ ] publish a new v0.3 release
- [ ] close reopened v0.3 trackers only after release acceptance

## Important rule

Automated PASS is necessary but not sufficient for release.

Do not infer human QA completion from ambiguous wording. Public release requires an explicit user acceptance of the manual QA checkpoint.
