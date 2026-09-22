# Proposal: Modernize the Main Dataset View Model/View Boundary

## Why

Stage 3 UX/UI modernization is active. The first OpenSpec pilot (PR #46) proved that a bounded presentation surface can move out of `app.py` while preserving the established application/backend seam.

The highest-leverage remaining presentation debt is now the main Dataset View. Its gallery is still an item-owned `QListWidget` inside `Window`, and `Window.refresh()` manually clears/rebuilds `QListWidgetItem` objects while also coordinating pagination, thumbnails, status presentation, filters and sorting.

That structure makes future layout/card/interaction improvements expensive and fragile. This change begins the main Dataset View migration using mature Qt Model/View primitives instead of inventing a custom UI framework.

Tracking: Issue #47.

## What Changes

- Introduce a dedicated Dataset View presentation module under `ui/qt`.
- Replace the main gallery's `QListWidgetItem` ownership with a `QAbstractListModel` + `QListView` seam.
- Represent stable sample identity and existing display/status metadata as model roles.
- Reuse the existing shared `ThumbnailWorker` / thumbnail cache behavior; do not invent a second thumbnail pipeline.
- Preserve the current `ViewSpec`, filter/sort, recommendation, manual-status and pagination semantics in this first migration slice.
- Keep current gallery shortcuts and user-visible behavior compatible unless a concrete parity blocker is recorded in the design first.
- Add offscreen/parity regression coverage for model rows, stable IDs, selection/actions and thumbnail updates.

## Explicitly Deferred

- Moving filter/sort semantics into `QSortFilterProxyModel` is a follow-on step after the list model/view seam is proven. The first slice must not duplicate the current `ViewSpec` logic merely to claim full Model/View adoption.
- Removing pagination in favor of continuous virtualized scrolling is deferred until there is measured evidence and an explicit user-visible behavior decision.
- Custom card painting with `QStyledItemDelegate` is deferred unless the default model/view presentation cannot preserve current behavior.
- No broad `Window` rewrite and no migration of Composite, Auto Crop or other dialogs in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This first slice is intentionally behavior-preserving and therefore sets `skip_specs: true`.
