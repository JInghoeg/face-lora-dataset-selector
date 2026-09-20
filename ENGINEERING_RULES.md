# Engineering Rules

These rules are project gates, not suggestions.

## 1. Mature-first

Before implementing a new capability:

1. Search for maintained open-source implementations, reference applications, libraries, model repositories, and relevant papers.
2. Inspect actual source/API, license, dependencies, runtime requirements, model weights, and redistribution terms.
3. Prefer direct reuse, vendoring, adaptation, parameter tuning, or a thin integration layer over reimplementation.
4. Do not write a custom algorithm merely because it appears smaller or easier to control.

If a mature implementation exists, custom replacement code requires an explicit written gap analysis and user approval before implementation.

## 2. Reuse means reuse

"Researching" an existing project is not enough.

When a mature implementation matches the need, use its actual:
- library/API,
- model weights,
- detector/segmenter,
- widget/canvas/editor code where license permits,
- data format or workflow primitives.

Our code should primarily provide product-specific glue: state, persistence, workflow, UI composition, export, and carefully justified adaptations.

## 3. Discuss before expensive execution

Before substantial implementation, freeze:
- exact user requirement,
- candidate mature solutions,
- why each candidate matches or fails,
- license and redistribution status,
- dependency/runtime cost,
- benchmark dataset,
- acceptance metrics,
- stop/go criteria,
- implementation boundary.

Do not build substantial UI, packaging, installers, CI, or compatibility layers for an unvalidated algorithm.

## 4. Small real validation first

New algorithms/models must first run on a small, representative real-world challenge set.

Only after the candidate passes that gate may it progress to:
1. full-dataset benchmark,
2. workflow integration,
3. production UI,
4. portable packaging.

A failed candidate is retired; do not keep tuning indefinitely unless the failure is clearly parameter-level and the user approves another round.

## 5. UI mature-first too

Before creating a custom editor, canvas, annotation widget, image viewer, crop tool, or interaction system:
1. inspect the current product for reusable components;
2. inspect mature open-source UI projects;
3. prefer vendoring/adapting compatible components over recreating interaction primitives.

Custom UI primitives require the same gap-analysis gate as custom algorithms.

## 6. Resource discipline

Optimize total project cost, not just runtime package size.

Cost includes:
- user time,
- implementation time,
- model downloads,
- disk usage,
- repeated dependency installs,
- CI cycles,
- debugging,
- tokens,
- rework risk.

Prefer staged evaluation so expensive/heavy candidates are only downloaded or integrated after cheaper mature candidates fail.

## 7. Evidence before confidence

Do not promote a candidate because it is theoretically suitable.

Promotion requires observed results on the user's real data and the agreed acceptance metrics.

## 8. Preserve user authority

Human review is authoritative. Automated outputs remain proposals until accepted.

## Pre-implementation gate

A PR that introduces a new algorithm, model, major UI primitive, or workflow must answer:

- What mature implementations were inspected?
- Which implementation are we directly reusing?
- What exact product-specific gap remains?
- Why can that gap not be solved by configuration/adaptation?
- What is the smallest real-data test?
- What are the stop/go metrics?
- What work is explicitly deferred until validation passes?
