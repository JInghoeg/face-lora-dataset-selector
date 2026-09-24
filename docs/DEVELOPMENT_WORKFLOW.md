# Development Workflow

This file is the durable operational project-management contract. Keep version-specific Issue/PR numbers in `docs/PROJECT_STATE.md`, not here.

## Sources of truth

Use, in priority order:
1. current user-confirmed product behavior and explicit acceptance;
2. current repository state/code;
3. active architecture/decision records;
4. current GitHub Issues/PRs;
5. validated automated and human QA evidence.

Chat summaries are navigation aids, not the authoritative product specification.

## Work item lifecycle

For meaningful work:
1. confirm/research the behavior;
2. write/freeze the decision in GitHub when needed;
3. create/update an Issue;
4. implement on a scoped branch;
5. open/update a Draft PR;
6. run automated checks;
7. classify human QA state;
8. make `docs/PROJECT_STATE.md` describe the expected post-merge canonical state when the task changes project state;
9. use `Closes #N` when the PR completes an Issue;
10. merge only at the appropriate checkpoint.

Normal work must not be committed directly to `main`.

Branch prefixes:
- `fix/` — bug fix
- `feature/` — product capability
- `refactor/` — behavior-preserving architecture
- `research/` — disposable benchmark/research
- `planning/` — product/research planning
- `chore/` — repository/process/build maintenance
- `docs/` — public/documentation-only work

## QA states

Never conflate automated and human validation.

Use exactly one:
- **AUTO PASS** — CI/self-tests passed; evidence only, not human acceptance.
- **HUMAN UNVERIFIED** — user-visible/runtime behavior changed but manual verification is deferred.
- **HUMAN PASS** — manually verified.
- **HUMAN NOT REQUIRED** — docs/process-only change that cannot alter runtime/user behavior.
- **IMMEDIATE HUMAN QA REQUIRED** — destructive/startup/release-critical risk; do not merge until resolved to HUMAN PASS.

For HUMAN UNVERIFIED, the PR must name the concrete QA debt/checkpoint Issue.

Immediate human QA is reserved for changes likely to:
- delete/overwrite source data;
- corrupt persistent state;
- break startup/Portable;
- cause irreversible workflow damage;
- block a release candidate.

The current QA checkpoint Issue, when one exists, is listed only in `docs/PROJECT_STATE.md`.

## Canonical manual-QA workspace

Portable human QA must use:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Prepare -RunId <verified-run-id>
```

Full rules: [MANUAL_QA.md](MANUAL_QA.md).

Do not create ad-hoc top-level QA folders. Disposable outputs belong under the managed QA workspace's `current\scratch`.

## Project-state synchronization

`docs/PROJECT_STATE.md` is the only canonical current-state document.

Rules:
- permanent workflow/architecture docs must not duplicate current release status;
- `.project/HANDOFF.md` is supplementary and must not duplicate canonical state;
- when a PR completes work, state edits describe the state expected **after that PR merges**;
- if an Issue closes with the PR, use `Closes #N`;
- if repository reality becomes newer than PROJECT_STATE, repair PROJECT_STATE before starting substantial work.

## Research-first / mature-first rule

Before custom work for a new model, algorithm, crop editor, task framework or UI primitive:
1. define the real product requirement and failure cost;
2. search authoritative docs/research and maintained implementations;
3. inspect actual APIs/source/license/runtime compatibility;
4. benchmark on a small real dataset;
5. define stop/go criteria;
6. reuse or wrap the mature implementation if it passes;
7. write custom code only for a documented gap.

Research output defaults to project/worktree drive under `_research_output/`; do not default large/repeated artifacts to C:.

## Architecture change rule

Architecture changes require an ADR when they:
- change dependency direction;
- introduce a new framework/runtime;
- change module/plugin discovery;
- change persistence ownership;
- change the UI/backend contract.

Small internal refactors that preserve the existing decision do not need a new ADR.

## Bilingual public documentation

`README.md` is the Simplified Chinese landing page and `docs/README.en.md` is the English landing page.

When public README content changes:
- update both language variants in the same PR;
- keep language-switch links valid;
- keep the advertised stable release version consistent;
- use the explicit README-sync exception only for a genuine language-specific/path-only change and explain why.

## Release discipline

Release preparation goes through a PR. Do not create a direct `main` release commit.

A release candidate must have:
- all release-gate features present;
- automated CI green;
- required human QA explicitly accepted;
- no unresolved destructive blockers;
- matching release notes;
- `.project/release_gate.json` updated to the target version with `status: APPROVED`, `human_qa: PASS`, acceptance date, and evidence.

After that release-preparation PR merges to `main`, the Windows Portable workflow may publish exactly that approved version. If the release already exists, automation must not silently overwrite it.

After publishing, a later state-sync PR may mark the gate `RELEASED`.

## Before declaring a checkpoint clean

Do not stop at “open Issues/PRs look clean”. Audit:
1. open Issues, PRs, and release state;
2. workflow triggers against current branches;
3. branch/ruleset enforcement;
4. stale branch/version/Issue references in active docs;
5. Project State vs actual repository reality;
6. release-gate state;
7. human-QA debt;
8. bilingual README synchronization;
9. root-layout and architecture invariants;
10. path-sensitive CI/script references after any move.

## PR checklist

Every PR should state:
- user-visible behavior changed? yes/no;
- modules affected;
- source-data risk;
- persistence/schema risk;
- automated tests added/run;
- exactly one human QA state;
- QA debt Issue when HUMAN UNVERIFIED;
- architecture contract impact;
- Project State impact + rationale;
- docs/issues updated;
- release impact when applicable.
