# Architecture

Status: ACTIVE — architecture baseline established in v0.3

## Goals

This project is a modular desktop application, not a collection of tightly coupled UI callbacks.

The architecture exists to support:
- fast feature iteration;
- optional features that can be added/removed without breaking unrelated features;
- replacement of model/runtime implementations behind narrow adapters;
- rapid UI/UX redesign without rewriting business logic;
- incremental work instead of whole-dataset refreshes;
- automated enforcement of dependency boundaries.

## Non-goals

- no microservices;
- no local HTTP server;
- no third-party plugin system yet;
- no full Clean Architecture ceremony;
- no rewrite of validated algorithms merely to fit a pattern.

## Chosen shape: modular monolith + lightweight ports/adapters

One process, one Portable application, one dataset state.

Dependency direction:

```
Qt UI / src/app_main.py + src/ui/qt
      |
      v
src/application/
      |
      +------> src/features/*
      |
      +------> src/infrastructure/*
                      ^
                      |
src/features/* --------+
      |
      v
src/core/
```

Rules:
1. `core` imports no feature, infrastructure, Qt, OpenCV or model runtime.
2. Feature packages are independent siblings and must not import one another.
3. Features may depend on `core` and narrow infrastructure adapters.
4. Infrastructure never imports product features or application orchestration.
5. Application may compose features and infrastructure.
6. New UI behavior should call the application facade instead of directly moving files, running models or editing caches.
7. Existing legacy code is migrated only at real pressure points; this is not an all-at-once rewrite.

## Current packages

### src/core/

Stable cross-layer DTOs and metadata. It must stay small.

Current:
- `src/core/contracts.py` — stable application/result DTOs.
- `src/core/models.py` — shared dataset/domain records (`Photo`, findings, view state); no Qt/model runtime imports.

Future domain records may move here only when doing so does not make Core depend on an optional feature.

### src/features/

Feature-first organization. Each feature owns its product-specific semantics.

Current:
- `src/features/ranking` — quality-analysis engine, duplicate grouping primitives used by the ranking pipeline, and automatic recommendation semantics; analysis is Qt-free.
- `src/features/composite` — Composite detector adapter and accept/materialization semantics.
- `src/features/auto_crop` — ISNetIS runtime, crop proposal/decision semantics and export crop metadata.
- `src/features/source_organizer` — dry-run planning, transaction/journal recovery and source organization semantics.
- `src/features/text_cleanup` — subtitle/watermark detection + repair as one feature: PP-OCR, suggestion policy, state persistence, MI-GAN/TELEA/NS repair and batch output.
- `src/features/duplicate` — duplicate grouping/review backend owned independently from Ranking and exposed through the Application boundary.

A feature should be removable without requiring edits inside sibling feature packages.

### src/infrastructure/

Generic implementation adapters.

Current:
- `src/infrastructure/filesystem.py` — generic file enumeration/copy/crop/archive/hash primitives.
- `src/infrastructure/cache_store.py` — versioned dataset cache serialization with feature codec injection.
- `src/infrastructure/model_download.py` — generic SHA-verified reusable model download/cache helper.

Feature-specific model runtimes remain inside their owning feature packages.

Infrastructure APIs must remain generic. Composite-specific naming and state belong in `src/features/composite`, not in filesystem infrastructure.

### src/application/

Workflow composition and stable in-process API consumed by UI.

Current:
- `SelectorApplication` — stable UI-facing in-process facade.
- `DatasetRefreshService` — incremental folder/cache/analysis orchestration with callbacks, no Qt.
- built-in `FeatureRegistry`

This is not a web API. It is an in-process boundary.

The registry is intentionally small. It describes built-in feature capabilities/contributions; it is not a dynamic third-party plugin loader.

### UI

The product implementation now lives under `src/`. The remaining large presentation/orchestration entry is `src/app_main.py`; extracted reusable Qt presentation lives under `src/ui/qt`. Root `app.py` is only a launcher/compatibility shim.

New UI/product actions should route through `SelectorApplication`. Continue moving presentation out of `src/app_main.py` incrementally, using `src/ui/qt` and Qt Model/View rather than making widgets own the dataset.

Qt explicitly recommends Model/View for flexible item presentation; convenience item widgets such as QListWidget are less flexible than view/model classes.

Reference:
https://doc.qt.io/qt-6/model-view-programming.html

## Repository ownership

- Product Python implementation: `src/`
- Tracked runtime models/catalogs: `resources/`
- Dependency manifests: `requirements/`
- Packaging: `packaging/`
- Developer/QA helpers: `tools/`
- Tests: `tests/`
- Root `app.py` and `text_detector.py`: compatibility/entry shims only

Do not grow new product implementation back into the repository root.

## Feature contribution model

A feature may contribute metadata such as:
- feature id;
- display name;
- whether it is optional;
- excluded source directories;
- later: actions, task types, review surfaces.

The application layer composes those contributions.

Example: Composite contributes `_CompositeSplit_Originals` as an excluded source root. Dataset enumeration does not need hard-coded Composite business logic.

## Application contracts

UI should migrate toward calls such as:

```
backend.active_image_files(folder)
backend.recompute_recommendations(records, target)
backend.accept_composite(folder, source, proposal, keep_mask)
backend.export_recommended(records, destination)
```

Return values are DTOs from `src/core/contracts.py`.

Do not add new UI methods that directly:
- call ONNX/model runtimes;
- move/archive source files;
- encode crop outputs;
- manipulate cache files;
- silently trigger global analysis.

## Background work

Current QThread worker-object usage remains valid. Qt officially supports moving worker QObjects to QThread and communicating via queued signals.

Reference:
https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html

Do not introduce another task framework until a measured gap exists.

Future task API should expose:
- stage/task name;
- current / total where known;
- current item;
- completion result;
- failure result;
- cancellation only where safe.

## Architecture enforcement

Import Linter runs in CI as a development-only dependency.

Contracts:
- Core cannot depend upward.
- Infrastructure cannot depend on features/application.
- Features cannot depend on application.
- Sibling feature packages are independent.

Reference:
https://import-linter.readthedocs.io/en/stable/contract_types/

## Future external plugins

Do not build a third-party plugin engine now.

If external independently installed plugins become a real requirement, prefer Python packaging Entry Points rather than inventing a discovery format.

Reference:
https://packaging.python.org/en/latest/specifications/entry-points/

## Stop condition for this architecture pass

The limited architecture pass stops when:

1. Shared dataset/domain records live outside Qt UI code.
2. Ranking/quality analysis is an independent Qt-free feature backend.
3. Composite product semantics are an independent optional feature.
4. Generic filesystem and cache persistence are infrastructure adapters.
5. Dataset refresh/incremental analysis are available through the Application API without importing Qt.
6. Existing Qt workers for the main dataset are thin adapters around Application services.
7. CI enforces feature independence, Qt-free backend packages and dependency direction.
8. There is a documented recipe for adding Auto Crop as a new feature without editing Ranking/Composite internals.

Then resume General Auto Crop Stage 2. Do not keep refactoring for aesthetics.
