# Proposal: Permanent Qt i18n Foundation

## Why

The current UI has presentation strings embedded directly in widgets. Stage 3 has begun replacing legacy presentation module-by-module, so fully translating the legacy UI now would create throwaway work.

Instead, establish the permanent i18n infrastructure once and require future modern UI modules to use it.

Tracking: Issue #52.

## Scope

- Qt `QTranslator` based language manager.
- Simplified Chinese is the source/default language.
- English is the first translation catalog.
- Language preference persists under the existing per-user application data root.
- Language switching is live; no application restart.
- Modern Qt modules support `QEvent.LanguageChange -> retranslate()`.
- Standard Qt `.ts -> .qm` compile/package path.
- Auto Crop / 自动裁剪 is the first fully integrated module.
- Direct v0.3 workflow surfaces exposed in the main shell use the same translation layer: Duplicate Group / 重复组, Composite Split / 组合图拆分, and Source Organizer / 整理源文件.
- Duplicate Review and Composite Split review surfaces support live retranslation where they are directly user-facing.
- Main window gets one global language selector and only a thin translated shell; the legacy selector UI is not mass-migrated.

## Non-goals

- no full translation of legacy `app.py` in this change;
- no backend/log/self-test/feature-key translation;
- no UI redesign;
- no duplicate translation framework;
- no restart-required language switching.

## Review

Initial English translations are candidates. User review/correction is required before closeout.
