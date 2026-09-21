# Project Handoff

Use this as a concise current continuation point, not a full chat transcript.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Branch: `feature/v0.3-workflow-recovery`
- Last verified code commit: `0d8c6952ed89f7dfbcf16ad2ec2bd16e791e9106` — merged PR #27 (Text Cleanup frontend/backend boundary)
- Working tree / uncommitted state: GitHub product branch is authoritative and merged. Local working tree was not inspected in this handoff; do not assume any local clone is current without `git fetch` / status check.
- Environment notes:
  - Windows 11 x64
  - Python: `G:\miniconda3` / Python 3.9
  - Current QA install: `G:\ComfyUI-aki\数据集\人脸LoRA数据集筛选器_v0.3测试\Face-LoRA-Dataset-Selector`
  - Auto Crop research clone: `G:\AI_Research\FaceLoRA_AutoCrop_Stage2`
  - Shared reusable model/download cache: `G:\AI_Research\_shared_cache\face-lora-dataset-selector\`
  - Original source dataset/tool folder must not be casually modified: `G:\ComfyUI-aki\数据集\人脸LoRA数据集筛选器`
  - Valby dataset: `G:\ComfyUI-aki\数据集\渥尔比`

## Current objective

Finish v0.3 without another architecture detour.

Immediate product gap is **General Auto Crop manual ROI editing**. Automatic proposal/review/export is implemented, but the originally required manual crop adjustment/reset workflow is still missing.

After manual ROI is implemented and automatically validated, build one consolidated Portable QA candidate and run the already-batched human QA checkpoint.

Architecture direction remains:
- feature-first modular monolith;
- Qt UI -> `SelectorApplication` -> independent feature backends;
- preserve mature/working algorithms;
- improve boundaries without rewriting stable functionality.

## What is verified complete

Only list behavior that has actually been implemented and checked.

- v0.3 recommendation semantics:
  - automatic recommendation baseline is independent of manual overrides;
  - effective status is manual override over automatic status;
  - F5/incremental refresh recomputes automatic recommendation correctly.
- Composite Split production workflow:
  - scans active effective 推荐 only;
  - accept materializes generated images immediately;
  - generated outputs support per-output 推荐 / 淘汰 selection;
  - accepted source moves to `_CompositeSplit_Originals\`;
  - archive is excluded from active dataset enumeration;
  - generated files are incrementally analyzed instead of triggering full-folder reanalysis.
- Auto Crop automatic backend:
  - post-Composite active 推荐 input;
  - ISNetIS production runtime;
  - alpha >= 0.10 mask support + fixed 32 px padding;
  - <5% removed-area no-op filter;
  - review states: pending / accepted / keep original;
  - source pixels are not modified;
  - accepted crop is materialized only during final export;
  - production runtime parity against `dghs-imgutils 0.19.0` passed.
- Auto Crop known limitation:
  - occasional foreground/background adhesion can make a proposal too loose;
  - intentionally recorded as non-blocking;
  - do not reopen Stage 3.2 unless real QA shows it is frequent.
- Source Organizer:
  - optional independent feature;
  - dry-run plan;
  - explicit confirmation;
  - 推荐 / 备选 / 淘汰 organization;
  - preserves origin relative path/source semantics;
  - ignores Composite archive;
  - transaction staging;
  - swap/cycle-safe rollback;
  - persisted journal and crash recovery before next dataset refresh;
  - successful organize does not rerun analysis models.
- Deferred UI interaction backlog:
  - per-image status changes no longer force page 1;
  - page clamps before slicing;
  - same-page scroll is restored;
  - custom recommendation target is a real exclusive mode;
  - custom numeric editor no longer includes the `自定义 ` prefix;
  - preset/custom target mode persists;
  - background refresh no longer overwrites target from the custom editor.
- Architecture boundary phase:
  - `core/`, `infrastructure/`, `application/`, and feature packages exist;
  - `SelectorApplication` is the UI/backend seam;
  - Import Linter enforces dependency direction, feature sibling independence, and backend no-Qt imports.
- Independent/current feature packages:
  - `features/ranking`
  - `features/composite`
  - `features/auto_crop`
  - `features/source_organizer`
  - `features/text_cleanup`
- Text Cleanup frontend/backend separation:
  - subtitle/watermark detection + repair intentionally remain one module;
  - PP-OCR detector moved under `features/text_cleanup`;
  - existing suggestion heuristic preserved;
  - state persistence moved behind backend;
  - MI-GAN / TELEA / Navier-Stokes moved behind backend;
  - batch filesystem output moved behind backend;
  - `SubtitleTab` now consumes `SelectorApplication` instead of directly owning model/cache/repair business logic;
  - removing the feature physically still allows main window startup without the tab.

## Validation performed

- Test / command:
  - Composite / Auto Crop / Source Organizer / UI regression GitHub Actions on Python 3.9 and 3.12.
  - Architecture Boundaries / Import Linter.
  - Auto Crop production runtime parity against `dghs-imgutils 0.19.0`.
  - Source Organizer tempfile transaction tests including true path swap, injected failure rollback, and persisted-journal crash recovery.
  - Text Cleanup Boundary workflow at head `7e7947040f593191cef678d23622e2b2bc49d712`.
  - Text Cleanup Portable build + packaged EXE self-test.
- Manual QA:
  - Stage 2 ISNetIS challenge set: HUMAN PASS.
  - Stage 3.1 contact-sheet review: materially improved; one residual foreground/background adhesion case recorded as non-blocking.
  - Consolidated v0.3 product changes remain in the batched HUMAN UNVERIFIED queue (#17).
  - Source Organizer has NOT yet been human-tested on original Valby data and must first be tested on a disposable/copied dataset.
- Result:
  - PR #27 Text Cleanup boundary merged successfully into product line.
  - PR #27 authoritative head checks all PASS:
    - Architecture Boundaries
    - Source Organizer regression
    - UI Polish regression
    - Auto Crop regression
    - Text Cleanup Boundary Python 3.9
    - Text Cleanup Boundary Python 3.12
    - optional Text Cleanup absence startup smoke
    - Portable build + Portable self-test
  - Text Cleanup QA artifact:
    - `text-cleanup-portable-qa`
    - artifact ID `10652222803`
    - compressed size `141,785,046` bytes

## Current blocker / uncertainty

- **Auto Crop manual ROI editing is not implemented.**
  - Current review only shows automatic proposal + crop preview and supports Accept / Keep Original / Restore Pending.
  - Missing:
    - draggable/resizable crop box;
    - save manually edited box;
    - reset manual box to automatic proposal;
    - export using the current accepted/manual box.
- Duplicate Review is still not a fully independent feature package:
  - duplicate grouping primitives remain under `features/ranking`;
  - `DuplicateReviewDialog` remains legacy Qt code in `app.py`.
  - This is architecture debt, not the immediate v0.3 product blocker.
- Qt presentation is still largely in one large `app.py`.
  - Main backend seam exists, but full frontend replacement is not yet as clean as the final desired `ui/qt` architecture.
  - Do not launch a broad UI rewrite before the v0.3 release gates are satisfied.
- Batched human QA and final Valby end-to-end QA are still pending.

## Immediate next action

Implement the smallest complete **Auto Crop manual ROI edit/reset workflow** on a new branch from `feature/v0.3-workflow-recovery`.

Required behavior:
1. automatic proposal initializes the editable ROI;
2. user can drag and resize the ROI;
3. user can accept the current ROI;
4. user can reset the ROI to the automatic proposal;
5. user can keep original;
6. manually edited crop box persists in Auto Crop feature state;
7. final export uses the accepted current box;
8. source pixels remain untouched until export;
9. Auto Crop remains an independent Qt-free backend feature;
10. add automated persistence/export regression and then create a new consolidated Portable QA candidate.

Prefer a mature Qt ROI implementation/pattern rather than custom drag-hit-testing. Verify dependency/package cost before adding a new runtime dependency.

## Relevant decisions

- Auto Crop production target / missing manual ROI:
  - https://github.com/JInghoeg/face-lora-dataset-selector/issues/21
- Batched human QA checkpoint:
  - https://github.com/JInghoeg/face-lora-dataset-selector/issues/17
- Text Cleanup frontend/backend separation:
  - https://github.com/JInghoeg/face-lora-dataset-selector/issues/26
  - https://github.com/JInghoeg/face-lora-dataset-selector/pull/27
- Architecture rules:
  - `docs/ARCHITECTURE.md`
  - `docs/MODULE_GUIDE.md`
  - `docs/DEVELOPMENT_WORKFLOW.md`
  - `docs/decisions/ADR-0001-modular-monolith.md`
- Current v0.3 roadmap:
  - `docs/ROADMAP_v0.3.md`

## Do not repeat

- Do not revive the failed custom Auto Crop Stage 1 saliency/pose safe-trim baseline.
  - Real Valby benchmark had ~0.62% crop suggestion coverage and high missed-crop rate.
- Do not use raw DeepGHS person bbox as final crop boundary.
  - Stage 1 showed it can cut hands, silhouette and props.
- Do not use every non-zero ISNetIS alpha pixel as foreground.
  - Soft background responses can expand bbox toward the full image.
- Do not restore the incorrect resolution-scaled 32/1024 padding.
  - Fixed 32 px performed materially better.
- Do not keep tuning the single foreground/background adhesion case now.
  - It is documented as non-blocking; revisit only if real QA shows it is common.
- Do not split Text Cleanup back into separate detection/repair product modules in this pass.
  - User explicitly chose one module because current functionality is already mature.
- Do not rewrite PP-OCR, suggestion heuristics, MI-GAN/TELEA/NS behavior during the boundary refactor.
- Do not add microservices/local HTTP/API-server ceremony.
  - Current architecture decision is a feature-first modular monolith + lightweight application/ports boundary.
- Do not start a large `app.py` / Qt Model-View rewrite before release blockers are cleared.
- Do not stop for manual QA after every non-fatal fix.
  - Record HUMAN UNVERIFIED items and test at a checkpoint.
- Do not test Source Organizer first on the original Valby dataset.
  - Use a disposable/copied dataset.
- Do not redownload reusable models/dependencies when a verified shared cache/file already exists.
- Do not default research/temp outputs to C:.

## User acceptance state

- User accepted the Stage 2 ISNetIS subject-protection result.
- User accepted Stage 3.1 as sufficiently improved and explicitly requested recording the remaining mask-adhesion issue instead of delaying development.
- User explicitly requested continued development rather than repeatedly stopping for non-fatal manual QA.
- User explicitly requires feature modularity and frontend/backend separation so features can be added/removed/fixed without broad ripple effects and UI can be redesigned later without rewriting backend logic.
- User corrected the project status: Auto Crop manual adjustment was missing and asked for a full completion/architecture audit.
- User explicitly requested that subtitle/watermark detection + subtitle/watermark repair remain **one module**, with frontend/backend separation only for now because those functions are already mature.
- That Text Cleanup boundary is now implemented, automatically validated, Portable-tested, and merged.
- User has NOT yet accepted v0.3 as release-complete.

## Notes for the next conversation

- Start by reading this file and `docs/ROADMAP_v0.3.md`; do not ask the user to restate the workflow.
- Product branch is `feature/v0.3-workflow-recovery`, current verified head `0d8c6952ed89f7dfbcf16ad2ec2bd16e791e9106`.
- PR #27 is already merged. Do not redo Text Cleanup separation.
- The immediate product blocker is Auto Crop manual ROI, not more mask research.
- Frozen workflow order:
  ```
  Initial analysis / recommendation
  -> Duplicate Review
  -> Composite Split
  -> General Auto Crop
  -> Optional Source Organizer
  -> Final Export
  ```
- Auto Crop only owns post-Composite single-subject active 推荐 images.
- `_CompositeSplit_Originals\` must remain excluded from every active-dataset operation.
- Source Organizer may move source locations but never modifies pixels.
- Final Export uses current active 推荐 only; accepted Auto Crop exports the crop, otherwise copies the active file.
- Human authority always overrides automatic suggestion.
- If doing architecture work after ROI, keep it bounded. Duplicate modularization is the next obvious architecture debt; the broad `ui/qt` migration can wait until v0.3 release gates are closed.
