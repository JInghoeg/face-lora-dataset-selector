# Proposal: Auto Crop Review Reusable UI Spike

## Why

v0.3 is close to release, but the new Auto Crop review surface is still visually and interactively closer to an engineering tool than a polished release surface.

This change is intentionally small: prove whether a mature reusable Qt visual layer can materially improve the existing Auto Crop review dialog without changing its backend, crop algorithm, persistence, export semantics, or validated pyqtgraph RectROI interaction.

Tracking: Issue #49.

## Product requirement

Usability and visual quality are equal hard requirements.

A result that is easy to use but visibly rough is not acceptable. A result that looks polished but weakens crop review interaction is also not acceptable.

## Reuse-first requirement

Before custom UI design:
- test mature reusable implementations/components against the real dialog;
- record license, maintenance/runtime fit, Python/PySide compatibility and integration cost;
- prefer actual library/theme/widget reuse over screenshot imitation;
- custom Qt styling/layout invention is fallback only after reusable options fail.

## First spike

Candidate A: qt-material 2.17.

Why it earns the first spike:
- BSD-2-Clause;
- supports PySide6 and Python 3.9;
- pure-Python wheel around 1.7 MB;
- only declared dependency is Jinja2;
- provides PyInstaller integration;
- can style a single dialog rather than forcing a whole-app theme migration.

The existing pyqtgraph RectROI remains the crop interaction implementation.

If the real rendered result is not visually strong enough, Candidate B is PySide6-Fluent-Widgets. Do not hand-write a replacement UI between candidates.

## Scope

- keep the current AutoCropReviewDialog structure and behavior for the first visual proof;
- render the real dialog with synthetic crop data under candidate themes;
- verify RectROI remains draggable/resizable and state-safe;
- capture screenshots as CI artifacts;
- measure dependency/Portable impact only after a visual candidate is worth adopting.

## Non-goals

- no Auto Crop backend/ISNetIS changes;
- no feature_state schema change;
- no Final Export change;
- no Duplicate/Composite/Text Cleanup redesign;
- no global theme migration;
- no generic Model/View continuation;
- no whole-app design system project.
