"""Compile Qt TS catalogs to QM runtime resources."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
TRANSLATIONS = ROOT / "translations"


def find_lrelease() -> str:
    names = ["pyside6-lrelease.exe", "pyside6-lrelease"]
    for name in names:
        sibling = Path(sys.executable).with_name(name)
        if sibling.exists():
            return str(sibling)
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "pyside6-lrelease was not found. Install the PySide6 runtime first."
    )


def main() -> int:
    tool = find_lrelease()
    sources = sorted(TRANSLATIONS.glob("app_*.ts"))
    if not sources:
        raise RuntimeError(f"No translation sources found in {TRANSLATIONS}")

    for ts_path in sources:
        qm_path = ts_path.with_suffix(".qm")
        subprocess.check_call(
            [tool, str(ts_path), "-qm", str(qm_path)]
        )
        if not qm_path.exists() or qm_path.stat().st_size <= 0:
            raise RuntimeError(f"Translation compile failed: {qm_path}")
        print(f"Compiled {ts_path.name} -> {qm_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
