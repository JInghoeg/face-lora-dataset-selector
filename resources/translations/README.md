# Translation workflow

The application uses Qt's native `QTranslator` runtime.

## Source language

- `zh_CN` is the source/default UI language.
- English is stored in `translations/app_en_US.ts`.
- Runtime `.qm` files are generated artifacts and are not committed.

## Compile

Run:

```powershell
python compile_translations.py
```

`安装.bat` and `build_portable.ps1` already run this automatically.

## Modern UI contract

When a UI module is modernized under `ui/qt`:

1. keep backend/application contracts locale-free;
2. put user-visible source text behind the module's translation context;
3. implement `retranslate()`;
4. handle `QEvent.LanguageChange` without rebuilding backend state;
5. add/update `.ts` entries;
6. extend i18n smoke/contract coverage.

Do not internationalize backend keys, model fields, algorithm state, self-test identifiers, or other internal protocol values.

## Current coverage

The permanent infrastructure is global. Complete translated presentation currently covers:

- the Auto Crop / 自动裁剪 modern UI;
- the thin main-window shell needed to select language and enter the Auto Crop workflow.

The remaining legacy UI should be migrated as each module receives its UX/UI modernization, rather than mass-refactoring presentation that will be replaced.
