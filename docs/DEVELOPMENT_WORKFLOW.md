# Development Workflow

This file is the operational project-management contract for future updates.

## Sources of truth

Use, in priority order:
1. current user-confirmed product behavior;
2. frozen architecture/decision docs;
3. current GitHub Issues/PRs;
4. validated tests and QA records;
5. implementation.

Chat summaries are navigation aids, not the authoritative product specification.

## Work item lifecycle

For meaningful work:
1. confirm/research the behavior;
2. write/freeze the decision in GitHub before implementation;
3. create/update an Issue;
4. implement on a scoped branch;
5. open/update a Draft PR;
6. run automated checks;
7. classify human QA state;
8. merge only at an appropriate checkpoint.

Branch prefixes:
- `fix/` — bug fix
- `feature/` — product capability
- `refactor/` — behavior-preserving architecture
- `research/` — disposable benchmark/research
- `planning/` — product/research planning

## QA states

Never conflate automated and human validation.

Use:
- **AUTO PASS** — CI/self-tests passed.
- **HUMAN UNVERIFIED** — not yet manually checked.
- **HUMAN PASS** — manually verified.
- **BLOCKED** — known blocker remains.

Non-fatal fixes with good automated coverage accumulate in the human-QA checkpoint Issue instead of stopping development after every fix.

Immediate human QA is reserved for changes likely to:
- delete/overwrite source data;
- corrupt persistent state;
- break startup/Portable;
- cause irreversible workflow damage;
- block a release candidate.

## QA checkpoint

Issue #17 currently owns the accumulated v0.3 human-QA queue.

At a checkpoint:
1. build one candidate;
2. test the whole accumulated checklist;
3. record PASS/FAIL per item;
4. fix failures;
5. avoid restarting manual QA for unrelated non-fatal fixes until the next checkpoint.



## Canonical manual-QA workspace

Portable human QA must use the repository helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Prepare -RunId <verified-run-id>
```

The helper owns the local QA workspace and cleanup policy. Full rules: [MANUAL_QA.md](MANUAL_QA.md).

Do **not** create ad-hoc top-level folders such as `G:\FaceLoRA-QA-<commit>` in future test instructions.

Default managed root is `G:\FaceLoRA-QA` when G: exists, with exactly one active candidate under `current`. The next Prepare removes the previous `current` automatically. Disposable test outputs belong in `current\scratch`.

Historical ad-hoc QA directories are cleaned with `CleanLegacy`, preview first and `-Force` only after the target list is visible.

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

## Update checklist

Every PR should state:
- user-visible behavior changed? yes/no;
- modules affected;
- source-data risk;
- persistence/schema risk;
- automated tests added/run;
- human QA status;
- architecture contract impact;
- docs/issues updated.

## Release discipline

A Portable artifact from an intermediate feature PR is not automatically a release candidate.

A release candidate must have:
- all release-gate features present;
- automated CI green;
- required human QA checkpoint complete;
- no unresolved destructive blockers;
- release notes / changelog updated.
