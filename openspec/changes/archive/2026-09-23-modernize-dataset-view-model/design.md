# Design: Main Dataset View Model/View Boundary

## Context

Current main Dataset View code lives largely in `app.py::Window`:

- `ReviewGrid(QListWidget)` owns mouse shortcut behavior.
- `Window.indices()` resolves the active `ViewSpec` through the existing application/backend boundary.
- `Window.refresh()` clamps pagination, clears the gallery, creates one `QListWidgetItem` per visible page row, decorates each item, maps record indexes, and starts thumbnail work.
- `ThumbnailWorker` is now a shared `ui/qt` presentation helper after PR #46.

Qt's official Model/View architecture provides the mature primitives needed here:
- `QAbstractListModel` for a one-dimensional model;
- `QListView` for list/icon presentation;
- `QSortFilterProxyModel` for later filtering/sorting separation;
- `QStyledItemDelegate` only when custom painting is actually necessary.

This change intentionally does not jump directly to the full proxy/delegate end state. It establishes the smallest safe model/view seam first.

## Goals / Non-Goals

Goals:
- remove `QListWidgetItem` as the main Dataset View state carrier;
- add a testable `DatasetListModel` with stable roles;
- add a `DatasetListView` that preserves current icon-grid interaction and shortcuts;
- keep `Window` responsible only for orchestration while row presentation moves into `ui/qt`;
- preserve existing filter/sort/pagination semantics and application/backend ownership;
- keep thumbnail work bounded and reuse the existing shared worker/cache path.

Non-goals:
- no recommendation/ranking changes;
- no `ViewSpec` semantic rewrite;
- no new filesystem/model/cache business logic in Qt classes;
- no pagination removal in this slice;
- no full `QSortFilterProxyModel` filter/sort migration yet;
- no new visual card design yet;
- no Composite/Auto Crop/Text Cleanup behavior changes;
- no broad `app.py` rewrite.

## Decisions

### Decision 1: Install the list model/view seam before moving filter/sort semantics

Create `ui/qt/dataset_view.py` with a `DatasetListModel(QAbstractListModel)` and a `DatasetListView(QListView)`.

The model receives the already-resolved current page rows from the existing orchestration path. It does not reimplement `ViewSpec` filtering or sorting.

Rationale: the current view/filter semantics are already working and tested behind the application boundary. Duplicating them inside a proxy during the first migration would create two sources of truth and make parity failures difficult to diagnose.

Follow-on direction: once model/view parity is proven, a later bounded change may move presentation filtering/sorting to `QSortFilterProxyModel` if doing so can reuse, rather than duplicate, the accepted `ViewSpec` semantics.

### Decision 2: Preserve pagination in the first slice

Keep the current page calculation and controls. The model represents the current page rather than all filtered rows.

Rationale: eliminating pagination is a user-visible interaction change and also changes thumbnail scheduling. It should be measured and decided explicitly, not smuggled into a refactor.

A later UX change may test `QListView.LayoutMode.Batched` / viewport-driven loading against real multi-thousand-image datasets and remove pagination only if the result is demonstrably better.

### Decision 3: Stable sample identity is the action key

Expose stable sample ID as a model role. Record index/path may be exposed as presentation roles for compatibility, but manual actions should resolve back to the current record through stable identity rather than trusting a stale visual row number across refreshes.

Rationale: model/proxy adoption changes row/index mapping. Stable identity prevents status actions from landing on the wrong sample after refresh/filter changes.

### Decision 4: Reuse the existing thumbnail pipeline

Keep `ThumbnailWorker` and existing cache path. Dataset View orchestration submits only the current page's missing thumbnails and updates model rows through `dataChanged` when images arrive.

No second cache or unbounded per-item worker system is introduced.

### Decision 5: Preserve current visual/interaction semantics before card redesign

The first slice retains:
- icon-grid layout;
- current display text/tooltips/status background meaning;
- click/double-click behavior;
- middle-click 推荐↔备选 shortcut;
- right-double-click 淘汰 shortcut;
- page and scroll preservation behavior.

If default `QListView` rendering cannot preserve a current semantic, use the smallest `QStyledItemDelegate` needed and record why.

## Risks / Trade-offs

- Stable-ID lookup may expose assumptions currently hidden by direct record indexes -> add parity tests around refresh/status changes.
- QListView signal/mouse behavior differs slightly from QListWidget -> add offscreen shortcut/action tests before removing the old grid.
- Thumbnail updates can target stale rows after page changes -> generation token + stable ID must gate model updates.
- Keeping pagination means the first slice does not yet realize the full proxy/virtualized-view design -> accepted intentionally to keep rollback small.
- Model roles can become a dumping ground -> expose only presentation data needed by the current view.

## Migration Plan

1. Add model/view parity tests around current page rows, identity and actions.
2. Add `DatasetListModel` and `DatasetListView` in `ui/qt/dataset_view.py`.
3. Reuse existing thumbnail worker/cache; update model rows through model signals.
4. Switch only the main Dataset gallery in `Window` to the new view.
5. Keep current filter/sort/page orchestration and visible behavior.
6. Run Python 3.9/3.12, UI regression, architecture boundary and full selector self-tests.
7. Verify the implementation against this design before considering proxy/filter or visual-card follow-ons.

Rollback: revert this bounded branch/PR. No dataset persistence migration is introduced.

## Follow-on Questions (not implementation blockers for this slice)

- Can the accepted `ViewSpec` semantics move cleanly into a `QSortFilterProxyModel` without duplicating domain/application logic?
- On real 3k+ datasets, does continuous batched QListView scrolling outperform and feel better than pagination once thumbnail loading is viewport-aware?
- What user-facing card/layout redesign should follow after the model/view seam is stable?
