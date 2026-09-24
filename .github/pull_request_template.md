## Summary

What does this PR change and why?

## Scope

Affected modules:
- [ ] ranking
- [ ] duplicates
- [ ] composite
- [ ] text cleanup
- [ ] auto crop
- [ ] organizer/export
- [ ] application/core/infrastructure
- [ ] UI only
- [ ] docs / repo hygiene

## Behavior / data risk

- User-visible behavior changed: YES / NO
- Source file mutation risk: NONE / LOW / HIGH
- Persistence/cache/schema risk: NONE / LOW / HIGH
- Startup/Portable risk: NONE / LOW / HIGH

## Architecture checklist

- [ ] Optional feature code does not import sibling feature internals.
- [ ] New UI code uses the application boundary rather than direct filesystem/model/cache calls.
- [ ] Generic infrastructure contains no feature-specific product policy.
- [ ] Local changes stay incremental when the changed set is known.
- [ ] Architecture docs/ADR updated if dependency direction changed.

## Validation

Automated:
- [ ] self-test / relevant unit coverage
- [ ] architecture CI
- [ ] runtime CI
- [ ] Portable smoke when required

Human QA:
- [ ] HUMAN PASS
- [ ] HUMAN UNVERIFIED — added to checkpoint Issue
- [ ] Immediate human QA required because destructive/startup/release blocker

## Project continuity

State impact:
- [ ] Yes — `docs/PROJECT_STATE.md` updated in this PR
- [ ] No — canonical current state is unchanged

Decision impact:
- [ ] None
- [ ] Existing/new Decision Record linked or updated

If this PR changes a current objective, verified capability, blocker, architecture/workflow boundary, QA debt, frozen/rejected path, or immediate next action, choose **Yes**.

## GitHub sync

- [ ] Relevant Issue updated when applicable.
- [ ] Decisions/product semantics recorded before merge when applicable.
- [ ] Roadmap/release notes updated if scope/status changed.
