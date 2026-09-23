# Project State

Canonical current-state entry point for the v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- v0.3 product stack merged to main at `521ac77f22996e2f160964da7c9b96f15ad29eaa`.
- Stage 4 consolidated human QA: **PASS / COMPLETE**.
- Issue #17: closed as completed.
- Current phase: **v0.3.0 release closeout**.

## Verified product state

Frozen workflow:

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

Architecture seam:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Feature packages:
- `features/ranking`
- `features/duplicate`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

Completed v0.3 scope includes Dataset/View workflow, stable sample IDs, Duplicate Review, AI Review Bundle, Composite Split, General Auto Crop + manual ROI, Source Organizer, Text Cleanup boundaries, Fluent Filmstrip Auto Crop UI, and permanent live Qt i18n.

## Human QA

Pinned Stage 4 QA candidate:
- code head: `46bc803b8a806d9c1cf61ab9a6534241ac0cff8e`
- workflow run: `35916370063`
- artifact ID: `10774289944`
- digest: `sha256:71835391390bcbe41199776565fbfecc9fc8d480af1f3dc4b60a9ca873c1c937`

User completed the consolidated checklist without reporting failures or blockers. Result: **PASS**.

No product-code fix was required after the human checkpoint. The later main integration and release-closeout changes are stack/documentation/release-engineering operations, not a change to the accepted product behavior.

## Release gate

v0.3.0 release requires:
1. release notes / changelog / README current;
2. generic release automation no longer hard-coded to v0.2.0;
3. final main Architecture Boundaries: PASS;
4. final Windows Portable build + packaged EXE self-test: PASS;
5. release artifact + SHA-256 attached to GitHub Release.

## Do not repeat

- Do not restart broad UX/UI modernization during release closeout.
- Do not repeat the entire Stage 4 manual QA unless product code changes.
- Do not test Source Organizer first on original irreplaceable data.
- Do not revive failed Auto Crop Stage 1 saliency/pose safe-trim.
- Do not split Text Cleanup detection/repair for this release.
- Do not add PySide6-Addons.
- Do not add microservices/local HTTP ceremony.

## Authoritative references

- `docs/ROADMAP_v0.3.md`
- `CHANGELOG.md`
- `RELEASE_NOTES_v0.3.0.md`
- Issue #17 — completed Stage 4 human QA.
- Issue #21 — Auto Crop tracking.
- Issue #23 — Source Organizer tracking.
- Issue #26 — Text Cleanup tracking.
