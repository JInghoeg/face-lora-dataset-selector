"""Offline stable incremental-update contract: no duplicate model download or dataset writes."""
from __future__ import annotations

import hashlib
import os
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "application" / "stable_update.py"
SPEC = importlib.util.spec_from_file_location("stable_update_under_test", MODULE)
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
assert SPEC.loader is not None
SPEC.loader.exec_module(updater)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rec(name: str, data: bytes):
    return {"relative": name, "size": len(data), "sha256": sha(data)}


def base_files():
    return {
        "VERSION.txt": b"v0.4.0\n",
        "Face LoRA Dataset Selector.exe": b"portable-exe-old",
        "_internal/models/person.onnx": b"unchanged-model-weight",
        "_internal/DirectML.dll": b"existing-provider",
    }


def next_files():
    result = dict(base_files())
    result["VERSION.txt"] = b"v0.4.1\n"
    result["Face LoRA Dataset Selector.exe"] = b"portable-exe-new"
    return result


def manifest_for(old, new, *, version_old="v0.4.0", version_new="v0.4.1"):
    return {
        "schema": 1,
        "from_version": version_old,
        "to_version": version_new,
        "base": [rec(k, v) for k, v in sorted(old.items())],
        "target": [rec(k, v) for k, v in sorted(new.items())],
        "changed": [k for k, v in new.items() if old.get(k) != v],
        "removed": [k for k in old if k not in new],
    }


def make_zip(path: Path, manifest, old, new):
    with ZipFile(path, "w", ZIP_DEFLATED) as out:
        out.writestr("manifest.json", json.dumps(manifest))
        for name in manifest["changed"]:
            out.writestr("files/" + name, new[name])


def check_main():
    # CI may itself run on the Windows system drive. Simulate a user data drive
    # for test fixtures without weakening the production system-drive guard.
    os.environ['SystemDrive'] = 'Z:'
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        app = root / "app"
        app.mkdir()
        old, new = base_files(), next_files()
        for name, data in old.items():
            path = app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        # Real state from v0.3.1 / user dataset must never change.
        saved = app / "_userdata" / "cache" / "my-dataset.json"
        saved.parent.mkdir(parents=True)
        saved.write_text('{"status":"推荐","reviewed":true}', encoding="utf-8")
        saved_sha = updater._hash_file(saved)
        delta = root / "source-delta.zip"
        manifest = manifest_for(old, new)
        make_zip(delta, manifest, old, new)
        delta_sha = updater._hash_file(delta)
        release = updater.Release(
            "v0.4.1", f"https://github.com/{updater.REPO}/releases/tag/v0.4.1",
            {updater.CATALOG_ASSET: f"https://github.com/{updater.REPO}/releases/download/v0.4.1/{updater.CATALOG_ASSET}",
             "delta.zip": f"https://github.com/{updater.REPO}/releases/download/v0.4.1/delta.zip"},
        )
        catalog = {"schema": 1, "release_version": "v0.4.1",
                   "deltas": [{"from_version": "v0.4.0", "to_version": "v0.4.1",
                               "asset": "delta.zip", "sha256": delta_sha}]}
        downloads = []

        def mock_download(url, destination, expected):
            assert expected == delta_sha and url.endswith("delta.zip")
            downloads.append(url)
            shutil.copy2(delta, destination)

        with patch.object(updater, 'latest_release', return_value=release), \
             patch.object(updater, '_read_json_response', return_value=catalog), \
             patch.object(updater, '_download', side_effect=mock_download):
            result = updater.check_and_prepare(app, force=True, now=1771000000)
        assert result.status == "staged", result
        assert len(downloads) == 1
        assert (root / ".face-lora-updates" / "pending.json").is_file()
        assert updater._hash_file(saved) == saved_sha
        assert (app / "_internal" / "models" / "person.onnx").read_bytes() == old["_internal/models/person.onnx"]
        assert (app / "VERSION.txt").read_bytes() == old["VERSION.txt"]
        assert set(manifest["changed"]) == {"VERSION.txt", "Face LoRA Dataset Selector.exe"}
        # Already staged: never download the same model/ZIP twice.
        with patch.object(updater, "latest_release", side_effect=AssertionError("unexpected network")):
            again = updater.check_and_prepare(app, force=False)
        assert again.status == "staged"
        # Missing per-version delta: do not fall back to full portable.
        (root / ".face-lora-updates" / "pending.json").unlink()
        no_delta = {"schema": 1, "release_version": "v0.4.1", "deltas": []}
        with patch.object(updater, 'latest_release', return_value=release), \
             patch.object(updater, '_read_json_response', return_value=no_delta), \
             patch.object(updater, '_download', side_effect=AssertionError('full download forbidden')):
            missing = updater.check_and_prepare(app, force=True, now=1771000100)
        assert missing.status == "no_delta"
        assert updater._hash_file(saved) == saved_sha
        # Corrupt source hash and model-dataset path traversal are rejected.
        bad = manifest_for(old, new)
        bad["changed"].append("_userdata/cache/my-dataset.json")
        try:
            updater.validate_delta_metadata(bad, "v0.4.0", "v0.4.1")
        except updater.UpdateError:
            pass
        else:
            raise AssertionError("Delta was allowed to touch user record cache.")
        try:
            updater.safe_relative("../dataset.jpg")
        except updater.UpdateError:
            pass
        else:
            raise AssertionError("Path traversal accepted.")
        delta_bad = root / "missing.zip"
        with ZipFile(delta_bad, "w", ZIP_DEFLATED) as out:
            out.writestr("manifest.json", json.dumps(manifest))
            out.writestr("files/VERSION.txt", new["VERSION.txt"])
        try:
            updater.validate_delta_file(delta_bad, "v0.4.0", "v0.4.1")
        except updater.UpdateError:
            pass
        else:
            raise AssertionError("Incomplete delta zip accepted.")
        (app / "VERSION.txt").write_bytes(b"v0.4.0-dev\n")
        with patch.object(updater, "latest_release", side_effect=AssertionError("dev builds must not update")):
            dev = updater.check_and_prepare(app, force=True)
        assert dev.status == "development"
        print("Stable update: delta-only, sha inventory, no repeated models, no dataset changes, dev isolation PASS")


if __name__ == "__main__":
    check_main()
