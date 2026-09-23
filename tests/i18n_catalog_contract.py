"""Static contract checks for the permanent Qt i18n catalog."""
from __future__ import annotations

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


def literal_calls(path: Path, method: str, quote: str):
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(method)}\(\s*{quote}([^\n{quote}]+){quote}"
    )
    return set(pattern.findall(text))


def main():
    data = catalog()
    assert "AutoCropReviewDialog" in data
    assert "CompositeSplitReviewDialog" in data
    assert "MainWindow" in data

    auto_sources = literal_calls(
        ROOT / "ui" / "qt" / "auto_crop_review.py",
        "self._tr",
        '"',
    )
    composite_sources = literal_calls(
        ROOT / "app.py",
        "self._tr_composite",
        "'",
    )
    main_sources = literal_calls(
        ROOT / "app.py",
        "self._tr_main",
        "'",
    )

    missing_auto = sorted(auto_sources - set(data["AutoCropReviewDialog"]))
    missing_composite = sorted(
        composite_sources - set(data["CompositeSplitReviewDialog"])
    )
    missing_main = sorted(main_sources - set(data["MainWindow"]))
    assert not missing_auto, f"Auto Crop i18n sources missing from TS: {missing_auto}"
    assert not missing_composite, (
        f"Composite Split i18n sources missing from TS: {missing_composite}"
    )
    assert not missing_main, f"MainWindow i18n sources missing from TS: {missing_main}"

    print(
        "i18n catalog contract OK:",
        len(data["AutoCropReviewDialog"]),
        "Auto Crop entries,",
        len(data["CompositeSplitReviewDialog"]),
        "Composite Split entries,",
        len(data["MainWindow"]),
        "MainWindow entries",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
