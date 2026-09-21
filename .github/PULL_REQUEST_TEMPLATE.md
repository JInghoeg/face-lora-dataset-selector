## Purpose

<!-- What real user/product problem does this PR solve? -->

## Scope

Affected modules:
- [ ] ranking
- [ ] duplicates
- [ ] composite
- [ ] text detection
- [ ] text repair
- [ ] auto crop
- [ ] organizer/export
- [ ] application/core/infrastructure
- [ ] UI only

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

## GitHub sync

- [ ] Relevant Issue updated.
- [ ] Decisions/product semantics recorded before merge.
- [ ] Roadmap/changelog updated if scope/status changed.
