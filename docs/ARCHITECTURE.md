# Architecture

Status: ACTIVE — v0.3 limited architecture boundary pass

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
Qt UI / app.py
      |
      v
application/
      |
      +------> features/*
      |
      +------> infrastructure/*
                  ^
                  |
features/* --------+
      |
      v
core/
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

### core/

Stable cross-layer DTOs and metadata. It must stay small.

Current:
- `core/contracts.py`

Future domain records may move here only when doing so does not make Core depend on an optional feature.

### features/

Feature-first organization. Each feature owns its product-specific semantics.

Current:
- `features/ranking` — automatic quality ranking/recommendation semantics.
- `features/composite` — Composite Split accept/materialization semantics.

Planned:
- `features/duplicates`
- `features/text_detection`
- `features/text_repair`
- `features/auto_crop`
- `features/organizer`

A feature should be removable without requiring edits inside sibling feature packages.

### infrastructure/

Generic implementation adapters.

Current:
- `infrastructure/filesystem.py`

Planned candidates when pressure justifies extraction:
- cache persistence;
- model runtime adapters;
- image decode/encode;
- external model download/cache.

Infrastructure APIs must remain generic. Composite-specific naming and state belong in `features/composite`, not in filesystem infrastructure.

### application/

Workflow composition and stable in-process API consumed by UI.

Current:
- `SelectorApplication`
- built-in `FeatureRegistry`

This is not a web API. It is an in-process boundary.

The registry is intentionally small. It describes built-in feature capabilities/contributions; it is not a dynamic third-party plugin loader.

### UI

The current Qt UI still lives largely in `app.py` and is legacy migration debt.

New UI/product actions should route through `SelectorApplication`. A later UX/UI phase should move presentation into a dedicated `ui/qt` package and use Qt Model/View rather than making widgets own the dataset.

Qt explicitly recommends Model/View for flexible item presentation; convenience item widgets such as QListWidget are less flexible than view/model classes.

Reference:
https://doc.qt.io/qt-6/model-view-programming.html

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

Return values are DTOs from `core/contracts.py`.

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

1. Ranking is an independent feature.
2. Composite product semantics are an independent feature.
3. Generic filesystem operations are infrastructure.
4. UI has an application facade for newly touched workflows.
5. CI enforces feature independence / dependency direction.
6. There is a documented recipe for adding Auto Crop as a new feature without editing Ranking/Composite internals.

Then resume General Auto Crop Stage 2. Do not keep refactoring for aesthetics.
