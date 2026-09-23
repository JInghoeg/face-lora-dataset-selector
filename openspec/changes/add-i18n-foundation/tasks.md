# Tasks

## 1. Infrastructure

- [x] 1.1 Add reusable LanguageManager using QTranslator.
- [x] 1.2 Persist global UI locale under the user application-data root.
- [x] 1.3 Add standard Qt TS/QM translation resource layout and compile helper.
- [x] 1.4 Package compiled translations in Portable.

## 2. First integration

- [x] 2.1 Add one global language selector to the main window shell.
- [x] 2.2 Make Auto Crop the first complete live-retranslated modern UI module.
- [x] 2.3 Keep legacy main-UI translation deliberately thin; do not mass-migrate obsolete presentation.

## 3. Verification

- [x] 3.1 Prove TS -> QM compilation on supported Python/PySide runtime.
- [x] 3.2 Verify locale preference persistence.
- [x] 3.3 Verify a live-open Auto Crop dialog switches zh_CN -> en_US -> zh_CN without restart.
- [x] 3.4 Verify backend state/records remain unchanged across language switch.
- [x] 3.5 Build Portable and verify packaged translation loads.

## 4. Review / closeout

- [ ] 4.1 Present initial English translations to user for wording review.
- [ ] 4.2 Apply user translation corrections.
- [ ] 4.3 Reconcile implementation against proposal/design/tasks.
- [ ] 4.4 Archive only after translation review and final CI.
