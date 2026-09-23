# Design: Extract Text Cleanup Presentation

## Context

See `proposal.md` for motivation and accepted phase order.

Current repository state already has:

```
SubtitleTab / thin Qt workers
        |
        v
SelectorApplication
        |
        v
features/text_cleanup
```

However the Qt side still resides in `app.py`:

- `TextScan`
- `TextCleanupBatchWorker`
- `ImagePreview`
- `SubtitleTab`
- `ThumbnailWorker`

Code inspection during planning found that `ImagePreview` is also used by Composite Review and `ThumbnailWorker` is also used by the main Dataset View. They are therefore shared presentation components, not Text Cleanup-owned classes.

The backend separation from PR #27 is already validated. This change must not redesign that backend.

## Goals / Non-Goals

Goals:

- create a real `ui/qt/text_cleanup.py` presentation module for Text Cleanup-specific Qt code;
- extract shared `ImagePreview` and `ThumbnailWorker` into reusable `ui/qt` modules instead of duplicating them;
- remove Text Cleanup-specific Qt classes from `app.py`;
- keep all Text Cleanup product behavior compatible;
- make UI dependencies explicit enough that the module can be imported and tested independently;
- keep the change small enough to revert cleanly.

Non-goals:

- no PP-OCR/model/repair algorithm changes;
- no Text Cleanup workflow redesign;
- no new threshold/default changes;
- no migration of unrelated MainWindow/Composite/Auto Crop presentation beyond replacing their references to the shared UI helpers;
- no broad Qt Model/View conversion in this slice;
- no change to Stage 4 Portable/QA sequencing.

## Decisions

### Decision 1: Extract one complete presentation surface plus genuinely shared UI helpers

Move `TextScan`, `TextCleanupBatchWorker`, and `SubtitleTab` into `ui/qt/text_cleanup.py`.

Move `ImagePreview` and `ThumbnailWorker` into small reusable sibling modules under `ui/qt`, then reuse those components from Text Cleanup and the existing Composite/main Dataset surfaces.

Rationale: the first draft incorrectly treated both helpers as Text Cleanup-owned. Code inspection showed real existing reuse, so forcing them into `text_cleanup.py` would create new coupling while pretending to remove old coupling.

Alternative considered: duplicate the helpers inside Text Cleanup. Rejected because that creates divergent UI implementations and future maintenance cost.

Alternative considered: move all remaining Qt presentation at once. Rejected because it turns a bounded pilot into a broad rewrite and makes regressions harder to localize.

### Decision 2: Inject application/backend dependencies

`SubtitleTab`, `TextScan`, and `TextCleanupBatchWorker` receive the existing `SelectorApplication` instance rather than importing `app.py.BACKEND`.

Presentation-only paths such as app directory and thumbnail cache are passed into the presentation/shared worker instead of reaching back into `app.py`.

Rationale: avoids circular imports and preserves the established UI -> application boundary.

### Decision 3: Preserve existing behavior before visual redesign

This slice is structural. Existing labels, controls, pagination behavior, manual box editing, state persistence, scan progress, repair preview, batch processing, and thumbnail behavior remain functionally equivalent.

Rationale: the first pilot needs a controlled baseline. Visual/interaction redesign can follow as separate OpenSpec changes where behavior requirements are explicit.

### Decision 4: Do not fabricate spec deltas

The change metadata sets `skip_specs: true` because user-visible behavior is intentionally unchanged.

Rationale: OpenSpec explicitly supports spec-less pure refactors; inventing a requirement solely to satisfy the workflow would defeat the purpose of testing a mature process honestly.

## Risks / Trade-offs

- **Risk: hidden dependency on app.py globals** -> Mitigation: inspect every moved class reference and inject/replace only the presentation dependencies actually required.
- **Risk: shared helper extraction changes Composite/main Dataset behavior** -> Mitigation: move code without semantic changes and keep call sites equivalent.
- **Risk: thumbnail/cache behavior changes during move** -> Mitigation: preserve existing cache-key/path logic and cover import/offscreen behavior plus existing Text Cleanup/UI regression.
- **Risk: accidental backend redesign** -> Mitigation: no edits under `features/text_cleanup` unless a concrete blocker is discovered and recorded in this design first.
- **Risk: pilot looks successful without running OpenSpec CLI** -> Mitigation: repository setup is provisional until `openspec validate --all --strict` runs in an environment with OpenSpec 1.13.1+ available.

## Migration Plan

1. Extract `ImagePreview` and `ThumbnailWorker` into reusable `ui/qt` modules with equivalent behavior.
2. Add `ui/qt/text_cleanup.py` with Text Cleanup-specific presentation classes and explicit dependencies.
3. Export the moved components from `ui/qt/__init__.py`.
4. Update `app.py` composition/imports and remove the migrated class definitions.
5. Run compile/self-tests, architecture checks, Text Cleanup boundary regression, UI regression, and an offscreen Text Cleanup UI smoke.
6. Keep the change on the pilot branch/Draft PR until a clean-context recovery test succeeds.

Rollback: revert the pilot commits/close the Draft PR. No dataset or persistence migration is introduced.

## Open Questions

None that change the current slice. Broader visual redesign and Qt Model/View adoption are intentionally deferred to later UX/UI changes after this pilot proves the workflow.
