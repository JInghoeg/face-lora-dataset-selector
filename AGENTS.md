# AGENTS.md

## Purpose

This is the active Face LoRA Dataset Selector product repository.

Treat repository state, code, Issues, PRs, and current user instruction as authoritative. Do not rely on chat memory alone.

## Required bootstrap

Before substantial work on an existing task:

1. read `docs/PROJECT_STATE.md`;
2. inspect the actual product branch and recent relevant merged/open/Draft PRs;
3. detect stale summaries before acting;
4. read `.project/HANDOFF.md` only as supplementary context;
5. follow only the Issues/Decision Records needed for the current task.

If repository reality is newer than PROJECT_STATE, repair PROJECT_STATE before relying on it.

## Repository change rule

- All normal repository changes go through a scoped branch + PR into `main`.
- Do not write directly to `main`.
- Release preparation also goes through a PR. Publishing is triggered only by the machine-readable `.project/release_gate.json` after explicit human acceptance.
- A completion PR must leave `docs/PROJECT_STATE.md` describing the expected **post-merge** canonical state, not the temporary pre-merge state.
- When a PR completes an Issue, prefer `Closes #N` in the PR body so Issue closure and post-merge state converge together.
- `.project/HANDOFF.md` must not duplicate current project state.

## Product branch

Stable product branch:
`main`

Current next-release umbrella:
Issue #60 — v0.4

## Architecture invariants

- Prefer feature-first modular boundaries.
- Qt presentation -> `SelectorApplication` -> feature backends.
- Backend feature packages must remain Qt-free.
- Optional feature removal should not destructively break unrelated modules.
- Do not introduce microservices/local HTTP merely to claim frontend/backend separation.
- Do not broaden a bounded feature extraction into a whole-application UI rewrite.

## Repository layout invariant

- Product implementation lives under `src/`.
- Tracked runtime assets live under `resources/`.
- Dependency manifests live under `requirements/`.
- `tests/`, `tools/`, `packaging/`, `docs/`, and `openspec/` own their respective concerns.
- Root-level `app.py` and `text_detector.py` are compatibility/entry shims only; do not grow product implementation back into them.
- Do not add a new top-level product directory just because no existing owner was checked first.
- Path moves are atomic: update imports, resources, CI, packaging, launch/install scripts, tests, and state in the same PR.

## Reuse-first

Before custom-building mature generic capability, inspect existing maintained solutions and verify fit, license, compatibility, and lifecycle cost.

## Validation cadence

Use risk-based validation:
- destructive/data-loss/startup/core-save-export/persistence risks require prompt human verification when automated confidence is insufficient;
- bounded reversible changes with relevant passing automation may remain HUMAN UNVERIFIED until an explicit checkpoint;
- deferred human QA must remain tracked in GitHub.

## Source/data safety

- Do not casually modify the original source tool folder.
- Source Organizer must be tested on a disposable/copied dataset before original Valby data.
- Prefer shared verified model/dependency caches.
- Research/temp output should not default to C:.

## Project continuity

Follow the Engineering-Playbook Project Continuity Protocol.

A state-changing task is not complete until current canonical state is synchronized. Prefer code + `docs/PROJECT_STATE.md` in the same PR.

Before declaring a release/checkpoint/repository cleanup complete, audit all of:
- open Issues and PRs;
- workflow triggers and required gates;
- stale branch/version/Issue references in active process docs;
- release-gate state;
- branch/ruleset enforcement;
- bilingual README synchronization;
- root-layout / architecture invariants.

Do not create duplicate CHECKPOINT files for history already preserved by Git.
