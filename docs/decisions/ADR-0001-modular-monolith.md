# ADR-0001 — Modular Monolith with Feature-First Boundaries

Status: Accepted
Date: 2026-09-21

## Context

The selector began as a small single-purpose PySide desktop app and accumulated independent capabilities:
- quality ranking/recommendation;
- near-duplicate review;
- Composite Split;
- text/watermark detection;
- text/watermark repair;
- AI review synchronization;
- planned Auto Crop;
- planned source organization.

Keeping product workflow, model runtime, file operations and UI callbacks in one `app.py` caused local changes to trigger global side effects and made UI iteration expensive.

The product remains a local Windows Portable app. Distributed services would add deployment complexity without solving a real requirement.

## Decision

Use a modular monolith with lightweight ports/adapters:

- organize product logic primarily by feature;
- keep sibling features independent;
- compose workflows in an application layer;
- isolate generic file/model/cache implementations as infrastructure;
- keep cross-layer contracts small and stable;
- expose an in-process application facade to UI;
- enforce dependency rules in CI.

Do not build a third-party plugin loader yet.

## Why this fits the product

It supports the real goals:
- add/remove features without destructive effects on siblings;
- fix one workflow locally;
- replace algorithms/runtimes behind adapters;
- redesign Qt UI without rewriting backend semantics;
- keep one process/Portable package;
- avoid microservice/plugin-framework overhead.

## Alternatives rejected

### Keep growing app.py
Rejected because QA already showed whole-dataset refresh/state coupling from local Composite actions.

### Pure horizontal folders only
Examples: `services/`, `workers/`, `dialogs/`.
Rejected as the primary organization because one feature would still be scattered across many technical folders.

### Microservices / local HTTP backend
Rejected: no deployment/distribution requirement justifies the extra boundary.

### Full dynamic plugin framework now
Rejected: no external third-party plugin ecosystem exists yet.

If that requirement appears later, Python Packaging Entry Points are the preferred discovery mechanism.

### Full rewrite
Rejected: validated behavior and models already exist; migration should happen at pressure points.

## Consequences

Positive:
- clearer ownership;
- local changes;
- easier testing;
- enforceable boundaries;
- easier future UI replacement.

Costs:
- some temporary legacy bridging remains in `app.py`;
- DTO/application contracts must be maintained;
- architecture CI adds a small development dependency.

## Stop rule

This ADR does not authorize unlimited refactoring.

Stop the current architecture pass when Auto Crop can be added as an independent feature through the documented application boundary without modifying Ranking/Composite internals.
