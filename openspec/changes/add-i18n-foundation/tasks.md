# Tasks

## 1. Infrastructure

- [ ] 1.1 Add reusable LanguageManager using QTranslator.
- [ ] 1.2 Persist global UI locale under the user application-data root.
- [ ] 1.3 Add standard Qt TS/QM translation resource layout and compile helper.
- [ ] 1.4 Package compiled translations in Portable.

## 2. First integration

- [ ] 2.1 Add one global language selector to the main window shell.
- [ ] 2.2 Make Auto Crop the first complete live-retranslated modern UI module.
- [ ] 2.3 Keep legacy main-UI translation deliberately thin; do not mass-migrate obsolete presentation.

## 3. Verification

- [ ] 3.1 Prove TS -> QM compilation on supported Python/PySide runtime.
- [ ] 3.2 Verify locale preference persistence.
- [ ] 3.3 Verify a live-open Auto Crop dialog switches zh_CN -> en_US -> zh_CN without restart.
- [ ] 3.4 Verify backend state/records remain unchanged across language switch.
- [ ] 3.5 Build Portable and verify packaged translation loads.

## 4. Review / closeout

- [ ] 4.1 Present initial English translations to user for wording review.
- [ ] 4.2 Apply user translation corrections.
- [ ] 4.3 Reconcile implementation against proposal/design/tasks.
- [ ] 4.4 Archive only after translation review and final CI.
