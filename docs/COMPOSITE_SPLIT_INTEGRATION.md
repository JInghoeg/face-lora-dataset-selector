# Composite Split — Production Integration

Research status: **PASS**

This document freezes the behavior validated by human QA before production implementation.

## Purpose

Convert composite character images into useful LoRA training assets without modifying source files.

## Validated behavior

- Independent multi-view / multi-person layouts:
  - detect N distinct character instances;
  - propose N separate outputs in deterministic reading order.

- Tightly overlapping multi-person compositions:
  - keep the group together;
  - crop once around the union of the group;
  - preserve a conservative outer margin.

- Noisy UI / thumbnail grids:
  - do not surface as Composite Split candidates.

- Duplicate / fragmented detections of one character:
  - suppress before proposing outputs.

- Partial-body / equipment composites without a reliable head signal:
  - do not surface as Composite Split candidates.

## Mature implementation reuse

Production must reuse the validated upstream detector stack:

- `dghs-imgutils`
- `deepghs/anime_person_detection`
- `deepghs/anime_head_detection`

Do not replace these with custom person/head detectors.

## Product rules

- Source images are never overwritten.
- Composite Split produces proposals first.
- Human confirmation remains authoritative.
- Research contact-sheet/benchmark code is not copied wholesale into production.
- Production code should contain only the minimum integration layer:
  detector adapter, proposal model, persistence, review workflow, and export handling.

## UI rule

Do not build a new image/crop interaction primitive from scratch.
Reuse an existing mature Qt component where practical.

## Acceptance

Production integration is complete only when:

1. validated four-view examples split into four usable outputs;
2. overlapping groups produce one group crop rather than N overlapping crops;
3. obvious UI thumbnail grids are not proposed;
4. duplicate same-person outputs are suppressed;
5. proposals can be accepted/rejected before export;
6. the original dataset folder remains unchanged until an explicit user action.
