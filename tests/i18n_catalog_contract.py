"""Static contract checks for the permanent Qt i18n catalog."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TS_PATH = ROOT / "translations" / "app_en_US.ts"
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def catalog():
    root = ET.parse(TS_PATH).getroot()
    result = {}
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        messages = {}
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.findtext("translation") or ""
            assert source, f"Empty source in {name}"
            assert translation, f"Empty translation for {name}: {source}"
            assert source not in messages, f"Duplicate source in {name}: {source}"
            assert set(PLACEHOLDER.findall(source)) == set(
                PLACEHOLDER.findall(translation)
            ), f"Placeholder mismatch: {name}: {source} -> {translation}"
            messages[source] = translation
        result[name] = messages
    return result


def literal_calls(path: Path, method: str):
    """Read literal translation calls using Python semantics, including newlines."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != method:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.add(first.value)
    return found


def main():
    data = catalog()
    for context in (
        "AutoCropReviewDialog",
        "CompositeSplitReviewDialog",
        "DuplicateReviewDialog",
        "MainWindow",
        "TextCleanupTab",
        "ImagePreview",
    ):
        assert context in data, context

    auto_sources = literal_calls(
        ROOT / "ui" / "qt" / "auto_crop_review.py",
        "_tr",
    )
    composite_sources = literal_calls(
        ROOT / "app.py",
        "_tr_composite",
    )
    duplicate_sources = literal_calls(
        ROOT / "ui" / "qt" / "duplicate_review.py",
        "_tr",
    )
    main_sources = literal_calls(
        ROOT / "app.py",
        "_tr_main",
    )
    text_cleanup_sources = literal_calls(
        ROOT / "ui" / "qt" / "text_cleanup.py",
        "_tr",
    )
    image_preview_sources = literal_calls(
        ROOT / "ui" / "qt" / "image_preview.py",
        "_tr",
    )

    checks = (
        ("Auto Crop", auto_sources, data["AutoCropReviewDialog"]),
        ("Composite Split", composite_sources, data["CompositeSplitReviewDialog"]),
        ("Duplicate Review", duplicate_sources, data["DuplicateReviewDialog"]),
        ("MainWindow", main_sources, data["MainWindow"]),
        ("Text Cleanup", text_cleanup_sources, data["TextCleanupTab"]),
        ("Image Preview", image_preview_sources, data["ImagePreview"]),
    )
    for label, sources, messages in checks:
        missing = sorted(sources - set(messages))
        assert not missing, f"{label} i18n sources missing from TS: {missing}"

    # Runtime strings with real line breaks must be represented by real line
    # breaks in TS. A literal backslash-n silently compiles but never matches.
    for context, messages in data.items():
        for source in messages:
            assert "\\n" not in source, (
                f"Literal backslash-n in TS source: {context}: {source!r}"
            )

    print(
        "i18n catalog contract OK:",
        ", ".join(
            f"{name}={len(data[name])}"
            for name in (
                "AutoCropReviewDialog",
                "CompositeSplitReviewDialog",
                "DuplicateReviewDialog",
                "MainWindow",
                "TextCleanupTab",
                "ImagePreview",
            )
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
