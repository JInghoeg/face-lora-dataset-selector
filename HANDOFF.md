# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `46bc803b8a806d9c1cf61ab9a6534241ac0cff8e` — PR #51.
- Current phase: **v0.3 Stage 4 — unified Portable + consolidated human QA**.
- Active tracker: Issue #17.
- Project Memory Gate remains active.

## Just completed

- PR #53 permanent live Qt i18n foundation merged and archived.
- PR #51 Fluent Filmstrip Auto Crop production adoption merged at `46bc803b`.
- Issue #49 closed.
- Auto Crop final UI accepted by user.
- Default candidate viewport is exactly one full row; additional rows appear only after splitter expansion.
- Python 3.9 / 3.12 production smoke and packaged Portable self-test pass.
- Stage 3 is complete.

## Pinned Stage 4 QA candidate

- code head: `46bc803b8a806d9c1cf61ab9a6534241ac0cff8e`
- workflow run: `35916370063`
- artifact: `auto-crop-fluent-portable-qa`
- artifact ID: `10774289944`
- digest: `sha256:71835391390bcbe41199776565fbfecc9fc8d480af1f3dc4b60a9ca873c1c937`
- artifact ZIP: `159,693,034 bytes`
- unpacked Portable: `357,015,371 bytes`
- expires: `2026-09-30T20:34:24Z`

Issue #17 contains the authoritative consolidated QA checklist.

## Immediate next action

1. Use the pinned unified Portable; do not rebuild merely for documentation-only changes.
2. Run Issue #17 in workflow order.
3. Source Organizer first human test must use a disposable/copied dataset, never original Valby data.
4. Record non-fatal findings and continue; stop immediately for startup/data-loss/source-mutation/state-loss/release blockers.
5. After checkpoint: blocker-only fixes -> affected CI + final Portable smoke -> real Valby end-to-end QA -> v0.3 release closeout.

## Relevant links

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — Stage 4 unified Portable + consolidated QA
- PR #15 — product-stack integration
- PR #51 / Issue #49 — completed Auto Crop Fluent Filmstrip + i18n
- Issue #21 — Auto Crop release tracking
- Issue #23 — Source Organizer release tracking
- Issue #26 — Text Cleanup release tracking
- Engineering-Playbook `PROJECT_CONTINUITY.md`
