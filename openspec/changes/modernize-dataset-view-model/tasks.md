# Tasks

## 1. Baseline and parity

- [x] 1.1 Add focused regression coverage that captures current Dataset View page membership/order, stable sample identity, status actions and page/scroll preservation before replacing the gallery widget.
- [x] 1.2 Confirm the first slice keeps existing `ViewSpec` filtering/sorting and pagination outside the model; verify no duplicate filter/sort implementation is introduced.

## 2. Dataset Model/View seam

- [x] 2.1 Add `ui/qt/dataset_view.py` with `DatasetListModel(QAbstractListModel)`; expose only the roles required for current icon, text, tooltip, status/background and stable sample identity.
- [x] 2.2 Add `DatasetListView(QListView)` in IconMode and preserve the existing click/double-click/middle-click/right-double-click interaction surface.
- [x] 2.3 Reuse shared `ThumbnailWorker` / cache behavior and update model rows through model signals; verify generation/stable-ID guards prevent stale thumbnail writes.
- [x] 2.4 Update `Window` to compose the new Dataset View while keeping current `ViewSpec`, page controls and application/backend calls unchanged.

## 3. Automated regression

- [ ] 3.1 Run compile + full selector self-test on Python 3.9 and 3.12.
- [ ] 3.2 Run/update UI Polish regression for pagination, custom target state and Dataset View interactions.
- [ ] 3.3 Run Architecture Boundaries / Import Linter; verify `ui/qt` still talks through `SelectorApplication` and does not acquire feature/backend/filesystem business logic.
- [ ] 3.4 Add an offscreen Dataset View smoke covering model roles, stable-ID action mapping and thumbnail update invalidation.

## 4. Verification / next decision

- [ ] 4.1 Verify implementation against proposal/design/tasks and record any mismatch before changing accepted intent.
- [ ] 4.2 Only after parity passes, decide the next bounded UX/UI change: proxy-based filter/sort migration, measured pagination removal/virtualization, or card/layout redesign. Do not silently bundle those follow-ons into this PR.
