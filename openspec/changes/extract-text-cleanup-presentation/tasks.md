# Tasks

## 1. OpenSpec pilot baseline

- [ ] 1.1 Add the OpenSpec project config and `extract-text-cleanup-presentation` change artifacts; verify the files follow the current spec-driven schema structure and record that CLI validation is still pending in this sandbox.
- [ ] 1.2 Open a Draft PR linked to Issue #45 and verify the old Issue-tree pilot (#41-#44) is closed/superseded so a fresh continuation sees only one active pilot.

## 2. Text Cleanup presentation extraction

- [ ] 2.1 Create `ui/qt/text_cleanup.py` containing the Text Cleanup Qt workers, preview, thumbnail worker, and tab; verify the module imports without importing feature internals or `app.py`.
- [ ] 2.2 Replace implicit `app.py.BACKEND`/presentation globals with explicit constructor dependencies while keeping calls on `SelectorApplication`; verify no backend feature package changes are required.
- [ ] 2.3 Update `app.py` and `ui/qt/__init__.py` to compose the moved tab and remove the migrated class definitions; verify startup/self-test still resolves the Text Cleanup tab.

## 3. Automated regression

- [ ] 3.1 Run Python compile plus the existing full selector self-test and Text Cleanup backend/boundary tests; verify all pass on the pilot head.
- [ ] 3.2 Add/run an offscreen Text Cleanup presentation smoke that instantiates the moved tab with `SelectorApplication`; verify no direct feature/infrastructure import boundary regression.
- [ ] 3.3 Run the existing Architecture Boundaries / Import Linter checks; verify UI remains presentation -> SelectorApplication rather than bypassing the application facade.

## 4. Continuity / drift test

- [ ] 4.1 In a clean-context continuation, recover the active change from repository artifacts without supplying the old chat plan; verify it identifies UX/UI as the active phase and does not jump directly to consolidated QA.
- [ ] 4.2 Inject one bounded QA finding or scope adjustment into this change, update the appropriate artifact, and verify accepted surrounding phase order remains unchanged.
- [ ] 4.3 Run `openspec validate --all --strict` with OpenSpec 1.13.1+ in an environment with registry/CLI access; verify strict validation passes before claiming the pilot complete.

## 5. Completion decision

- [ ] 5.1 Verify implementation against proposal/design/tasks (use `/opsx:verify` when expanded workflows are available) and record any mismatch instead of silently updating history.
- [ ] 5.2 Only after the recovery + change-evolution tests pass, decide whether to archive this change and whether any lesson is mature enough to consider for Engineering-Playbook; verify no Playbook modification exists before that decision.
