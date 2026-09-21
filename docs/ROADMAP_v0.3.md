# v0.3 Roadmap

Status date: 2026-09-21

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Duplicate Review workflow.
- AI Review Bundle / patch workflow.
- Composite Split detector research and production integration.
- Composite source archive semantics.
- Composite per-output keep/reject behavior.
- generated-files-only incremental analysis after Composite Review.
- automatic recommendation baseline separated from final manual override.
- batched non-fatal human-QA policy.

Some recent interaction fixes are AUTO PASS but HUMAN UNVERIFIED; see Issue #17.

## Current

### Limited architecture boundary pass

Goal: prepare for Auto Crop, Organizer and later UX/UI work without a rewrite.

Implemented in the current pass:
- feature-first Ranking and Composite boundaries;
- shared domain models outside Qt;
- generic filesystem + dataset cache infrastructure;
- Qt-free quality analysis engine;
- Qt-free incremental dataset refresh service;
- stable `SelectorApplication` facade for touched workflows;
- architecture CI + optional-Composite startup smoke;
- project/update/QA workflow documentation.

Stop conditions are defined in `docs/ARCHITECTURE.md`. After the final automated architecture/runtime/Portable checks pass, this refactor stops and Stage 2 Auto Crop research resumes.

Draft PR: #18
Tracking Issue: #17

## Next

### General Auto Crop Stage 2 research

Resume the previously frozen research:
1. exact prior challenge cases;
2. ISNetIS raw mask validation;
3. inspect hair/hands/feet/skirt/weapons/accessories protection;
4. if sufficient, research/reuse a mature mask-to-safe-crop implementation;
5. if insufficient on props/weapons, escalate to GroundingDINO + SAM as previously planned;
6. no production Auto Crop algorithm before real-data PASS.

### Auto Crop production module

Only after research PASS:
- `features/auto_crop`
- background task
- persisted proposal/decision state
- Auto Crop Review UI
- final export application

### Source Organizer

Separate optional module:
- organize active source images into 推荐 / 备选 / 淘汰;
- never modify pixels;
- never touch Composite source archive;
- preserve cache/sample identity across moves.

### UX/UI quality upgrade

After backend/application boundaries are stable:
- migrate dataset presentation toward Qt Model/View;
- preserve state across local updates;
- reuse mature/open-source Qt components when appropriate;
- UI depends on application/DTOs, not filesystem/model runtimes.

## Deferred UI backlog

Issue #16:
- page reset on status changes;
- explicit custom-target state;
- custom numeric input prefix/edit behavior;
- broader explicit background progress.

## Human QA checkpoint

Issue #17 accumulates non-fatal unverified fixes.

Do not force a new manual QA build after each minor correction.

## v0.3 release gate

v0.3 is not final until:
- architecture pass stops at its defined boundary;
- General Auto Crop backend passes real-data validation;
- Auto Crop Review integrated;
- Source Organizer integrated;
- final export applies Auto Crop over active recommended images;
- accumulated human-QA checkpoint passes;
- final local Valby workflow QA passes.
