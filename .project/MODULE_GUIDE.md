# Adding or Updating a Feature Module

Use this checklist when adding a feature such as Auto Crop.

## 1. Define the feature boundary

Write down:
- input scope;
- output/result;
- persisted state;
- filesystem effects;
- background work;
- human review point;
- downstream consumers.

If another feature must understand this feature's internals, the boundary is wrong.

## 2. Create the feature package

Preferred shape:

```
src/features/<feature_id>/
    __init__.py
    service.py
    # optional detector.py / policy.py / contracts.py only when needed
```

Do not create files merely to satisfy a template.

## 3. Use generic infrastructure

A feature may use generic adapters:
- file copy/move/crop;
- cache store;
- model runtime;
- downloads.

Do not put feature-specific business names/rules into generic infrastructure.

## 4. Return explicit results

Prefer explicit DTOs over hidden global refreshes.

Example:

```
result = backend.accept_composite(...)
result.archived_source
result.outputs
```

The application/UI decides how to update presentation state.

## 5. Register contributions

If the feature contributes source exclusions/actions/task types, register them through the application feature registry.

Do not hard-code optional feature knowledge into unrelated modules.

## 6. UI integration

New UI code calls `SelectorApplication`.

Do not introduce new direct UI calls to:
- filesystem mutation;
- cache implementation;
- model runtime;
- sibling feature internals.

## 7. Background task

For expensive work:
- run outside the GUI thread;
- emit explicit progress;
- operate only on the known changed set when possible;
- do not fall back to a full dataset scan unless required.

## 8. Tests / architecture

Add:
- behavior/self-test coverage;
- architecture contract if a new package boundary is introduced;
- real-data benchmark before production for model/algorithm features.

## 9. GitHub project management

Before implementation:
- update/create Issue;
- record product semantics;
- research mature alternatives.

During implementation:
- scoped branch + Draft PR;
- automated CI.

After implementation:
- mark AUTO PASS;
- add to HUMAN UNVERIFIED checkpoint unless immediate human QA is required.
