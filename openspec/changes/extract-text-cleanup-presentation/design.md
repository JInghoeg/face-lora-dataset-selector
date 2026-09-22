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

The backend separation from PR #27 is already validated. This change must not redesign that backend.

## Goals / Non-Goals

Goals:

- create a real `ui/qt/text_cleanup.py` presentation module;
- remove Text Cleanup Qt classes from `app.py`;
- keep all Text Cleanup product behavior compatible;
- make UI dependencies explicit enough that the module can be imported and tested independently;
- keep the change small enough to revert cleanly.

Non-goals:

- no PP-OCR/model/repair algorithm changes;
- no Text Cleanup workflow redesign;
- no new threshold/default changes;
- no migration of unrelated MainWindow/Composite/Auto Crop presentation;
- no broad Qt Model/View conversion in this slice;
- no change to Stage 4 Portable/QA sequencing.

## Decisions

### Decision 1: Move one complete presentation surface, not scattered helpers

Move the Text Cleanup Qt workers, preview, thumbnail worker, and `SubtitleTab` together into `ui/qt/text_cleanup.py`.

Rationale: moving only one helper would reduce line count but leave the presentation lifecycle coupled to `app.py`. Moving the whole already-separated Text Cleanup surface creates a meaningful module boundary without touching unrelated UI.

Alternative considered: move all remaining Qt presentation at once. Rejected because it turns a bounded pilot into a broad rewrite and makes regressions harder to localize.

### Decision 2: Inject application/backend dependencies

`SubtitleTab`, `TextScan`, and `TextCleanupBatchWorker` receive the existing `SelectorApplication` instance rather than importing `app.py.BACKEND`.

Presentation-only paths such as app directory / thumbnail cache are passed or derived locally without changing backend APIs.

Rationale: avoids circular imports and preserves the established UI -> application boundary.

### Decision 3: Preserve existing behavior before visual redesign

This slice is structural. Existing labels, controls, pagination behavior, manual box editing, state persistence, scan progress, repair preview, batch processing, and thumbnail behavior remain functionally equivalent.

Rationale: the first pilot needs a controlled baseline. Visual/interaction redesign can follow as separate OpenSpec changes where behavior requirements are explicit.

### Decision 4: Do not fabricate spec deltas

The change metadata sets `skip_specs: true` because user-visible behavior is intentionally unchanged.

Rationale: OpenSpec explicitly supports spec-less pure refactors; inventing a requirement solely to satisfy the workflow would defeat the purpose of testing a mature process honestly.

## Risks / Trade-offs

- **Risk: hidden dependency on app.py globals** -> Mitigation: inspect every moved class reference and inject/replace only the presentation dependencies actually required.
- **Risk: thumbnail/cache behavior changes during move** -> Mitigation: preserve existing cache key/path logic and cover import/offscreen behavior plus existing Text Cleanup regression.
- **Risk: accidental backend redesign** -> Mitigation: no edits under `features/text_cleanup` unless a concrete blocker is discovered and recorded in this design first.
- **Risk: pilot looks successful without running OpenSpec CLI** -> Mitigation: repository setup is provisional until `openspec validate --all --strict` runs in an environment with OpenSpec 1.13.1+ available.

## Migration Plan

1. Add `ui/qt/text_cleanup.py` with moved presentation classes.
2. Export the tab from `ui/qt/__init__.py`.
3. Update `app.py` composition/imports and remove the migrated classes.
4. Run compile/self-tests, architecture checks, Text Cleanup boundary regression, and an offscreen UI smoke.
5. Keep the change on the pilot branch/Draft PR until a clean-context recovery test succeeds.

Rollback: revert the pilot commits/close the Draft PR. No dataset or persistence migration is introduced.

## Open Questions

None that change the current slice. Broader visual redesign and Qt Model/View adoption are intentionally deferred to later UX/UI changes after this pilot proves the workflow.
