# Design: Permanent Qt i18n Foundation

## Runtime architecture

```text
QApplication
    ↓
LanguageManager (QObject)
    ├─ QSettings-compatible INI preference
    ├─ QTranslator
    ├─ languageChanged(locale)
    └─ install/remove translator
            ↓
QEvent.LanguageChange
            ↓
modern ui/qt module retranslate()
```

The backend and `SelectorApplication` remain unaware of locale.

## Persistence

Store UI preference at:
`%LOCALAPPDATA%/Face LoRA Dataset Selector/ui.ini`

This is application-level presentation state, not dataset state.

## Translation resources

- source/default language: `zh_CN`;
- first translated language: `en_US`;
- source catalog: `translations/app_en_US.ts`;
- runtime catalog: `translations/app_en_US.qm`;
- `.qm` is compiled with Qt `lrelease` during installation/build/CI.

## Live switching

Installing/removing `QTranslator` triggers Qt `LanguageChange` events.

Modern widgets implement:
- `retranslate()` for static presentation text;
- `changeEvent()` calls `retranslate()` on `QEvent.LanguageChange`;
- dynamic status text calls the same translation context when regenerated.

No dataset reload, backend reconstruction or restart is required.

## First integration

### Auto Crop / 自动裁剪

The complete modern Auto Crop dialog becomes the reference implementation.

It translates:
- window/header labels;
- actions;
- theme tooltips;
- candidate decision/status labels;
- dynamic info strings;
- user-facing validation messages.

### Legacy shell bridge

The current main window gets:
- a compact global language selector;
- translated top-level window/tab labels and Auto Crop entry where practical.

Do not comprehensively migrate the legacy controls. Their full translation should arrive when those modules receive their own UX/UI modernization.

## Future contract

New/refactored `ui/qt` modules must:
1. avoid new user-visible hard-coded text that cannot be retranslated;
2. implement a `retranslate()` boundary;
3. respond to `QEvent.LanguageChange`;
4. add catalog entries and i18n smoke coverage.

## Packaging

Portable includes compiled `.qm` resources. Source installer compiles translations after installing PySide6 runtime.

CI proves:
- translation compile works with supported runtime;
- preference persists;
- existing dialog changes language live;
- switching back to Chinese restores source text;
- Portable self-test still passes.
