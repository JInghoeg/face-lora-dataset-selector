"""Stable GitHub Release update discovery and strict file-delta preparation.

No update work touches LoRA source images, existing records or model caches.
The running process only downloads and verifies a delta; the bundled Windows
helper applies it after the application has shut down.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Mapping, Optional
from urllib.request import Request, urlopen
from zipfile import ZipFile


REPO = "JInghoeg/face-lora-dataset-selector"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
CATALOG_ASSET = "FaceLoRA-Incremental-v1.json"
HELPER_RELATIVE = Path("updater") / "apply-update.ps1"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
HEX_RE = re.compile(r"^[a-f0-9]{64}$")
MAX_METADATA = 1024 * 1024
MAX_DELTA_BYTES = 1024 * 1024 * 1024
CHECK_INTERVAL_SECONDS = 12 * 60 * 60
MUTABLE_PARTS = {
    "_userdata", "cache", "logs", "_FaceLoRA_ModelCache",
    ".face-lora-updates", ".updates", "startup-error.txt",
}


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    tag: str
    page_url: str
    assets: Mapping[str, str]


@dataclass(frozen=True)
class CheckResult:
    status: str
    current: str
    latest: str = ""
    url: str = ""
    detail: str = ""
    download_bytes: Optional[int] = None


def app_version(app_root: Path) -> str:
    path = Path(app_root) / "VERSION.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "v0.4.0-dev"
    return value if VERSION_RE.fullmatch(value) else "v0.4.0-dev"


def is_newer(latest: str, current: str) -> bool:
    new, old = VERSION_RE.fullmatch(latest), VERSION_RE.fullmatch(current)
    return bool(new and old and tuple(map(int, new.groups())) > tuple(map(int, old.groups())))


def safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value and "/" in value:
        raise UpdateError("Invalid delta path.")
    win = PureWindowsPath(value)
    # ZIP/JSON may contain slash-separated paths, never drives or UNC paths.
    if win.is_absolute() or win.drive or value.startswith(("/", "\\")) or ":" in value:
        raise UpdateError("Absolute delta paths are forbidden.")
    parts = value.replace("\\", "/").split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise UpdateError("Traversal or empty delta path.")
    if parts[0].casefold() in {x.casefold() for x in MUTABLE_PARTS}:
        raise UpdateError("Update may not change user state.")
    if parts[0].startswith(".") and parts[0] != ".update-version":
        raise UpdateError("Undeclared hidden file in update.")
    return Path(*parts)


def _require_hash(value: str) -> str:
    if not isinstance(value, str) or not HEX_RE.fullmatch(value.lower()):
        raise UpdateError("Malformed SHA-256 in update manifest.")
    return value.lower()


def _read_json_response(url: str, *, limit: int = MAX_METADATA) -> Any:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "FaceLoRA-Updates/1"})
    with urlopen(request, timeout=8) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError("Update metadata exceeds safety limit.")
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("Invalid GitHub update metadata.") from exc


def latest_release() -> Release:
    payload = _read_json_response(LATEST_API)
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("Latest GitHub release is not a stable release.")
    tag = str(payload.get("tag_name", ""))
    if not VERSION_RE.fullmatch(tag):
        raise UpdateError("Stable release has an unexpected version.")
    url = str(payload.get("html_url", ""))
    if not url.startswith(f"https://github.com/{REPO}/releases/tag/"):
        raise UpdateError("GitHub release page is not trusted.")
    assets: dict[str, str] = {}
    for item in payload.get("assets", []):
        if not isinstance(item, dict):
            continue
        name, link = str(item.get("name", "")), str(item.get("browser_download_url", ""))
        if link.startswith(f"https://github.com/{REPO}/releases/download/"):
            assets[name] = link
    return Release(tag, url, assets)


def _hash_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(str(temp), str(path))


def _storage(app_root: Path) -> Path:
    root = Path(app_root).resolve()
    if not (root / "VERSION.txt").is_file():
        raise UpdateError("Versioned Portable required for automatic updates.")
    if os.name == "nt":
        drive = root.drive
        if drive and drive.casefold() == os.environ.get("SystemDrive", "C:").casefold():
            raise UpdateError("Automatic update scratch space cannot be placed on the system drive.")
    storage = root.parent / ".face-lora-updates"
    if storage.resolve() == root or root in storage.parents:
        raise UpdateError("Unsafe update staging directory.")
    return storage


def _entry_index(entries: Any) -> dict[str, tuple[str, int]]:
    if not isinstance(entries, list) or not (1 <= len(entries) <= 10000):
        raise UpdateError("Delta inventory is missing or oversized.")
    result: dict[str, tuple[str, int]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise UpdateError("Invalid delta inventory item.")
        rel = str(item.get("relative", ""))
        safe_relative(rel)
        canonical = rel.replace("\\", "/").casefold()
        size = item.get("size")
        if canonical in result or type(size) is not int or not 0 <= size < MAX_DELTA_BYTES:
            raise UpdateError("Duplicate or invalid delta inventory item.")
        result[canonical] = (_require_hash(item.get("sha256", "")), size)
    return result


def validate_delta_metadata(manifest: Any, old_version: str, new_version: str) -> tuple[dict, dict, set]:
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise UpdateError("Unsupported update manifest schema.")
    if manifest.get("from_version") != old_version or manifest.get("to_version") != new_version:
        raise UpdateError("Update's source/target version does not match this installation.")
    base, target = _entry_index(manifest.get("base")), _entry_index(manifest.get("target"))
    changed = manifest.get("changed")
    if not isinstance(changed, list):
        raise UpdateError("Update does not declare changed files.")
    differences = {k for k, v in target.items() if k not in base or base[k] != v}
    declared: set[str] = set()
    for name in changed:
        safe_relative(name)
        key = name.replace("\\", "/").casefold()
        if key in declared:
            raise UpdateError("Duplicate changed file.")
        declared.add(key)
    if differences != declared:
        raise UpdateError("Delta changed-file list differs from SHA inventory.")
    removed = manifest.get("removed", [])
    if not isinstance(removed, list):
        raise UpdateError("Invalid removed-file list.")
    for name in removed:
        safe_relative(name)
        key = name.replace("\\", "/").casefold()
        if key not in base or key in target:
            raise UpdateError("Invalid removed-file entry.")
    if len(removed) != len(set(x.replace("\\", "/").casefold() for x in removed)):
        raise UpdateError("Duplicate removed file.")
    if set(base) - set(target) != {x.replace("\\", "/").casefold() for x in removed}:
        raise UpdateError("Removed-file list differs from SHA inventory.")
    return base, target, declared


def validate_delta_file(zip_path: Path, old_version: str, new_version: str) -> dict:
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        if "manifest.json" not in names or len(names) > 10030:
            raise UpdateError("Delta archive has no valid inventory.")
        with archive.open("manifest.json") as handle:
            data = handle.read(MAX_METADATA + 1)
        if len(data) > MAX_METADATA:
            raise UpdateError("Delta inventory exceeds limit.")
        manifest = json.loads(data.decode("utf-8-sig"))
        _, target, changed = validate_delta_metadata(manifest, old_version, new_version)
        actual = set()
        for info in archive.infolist():
            if info.filename == "manifest.json":
                continue
            if info.is_dir() or not info.filename.startswith("files/"):
                raise UpdateError("Update archive contains unexpected entries.")
            name = info.filename[6:]
            safe_relative(name)
            key = name.replace("\\", "/").casefold()
            if key in actual or key not in changed:
                raise UpdateError("Update archive contains undeclared or repeated files.")
            if info.file_size != target[key][1]:
                raise UpdateError("Changed-file size differs from manifest.")
            actual.add(key)
        if actual != changed:
            raise UpdateError("Update archive is missing changed files.")
        return manifest


def _verify_local_base(app_root: Path, manifest: dict) -> None:
    base, _, _ = validate_delta_metadata(
        manifest, manifest["from_version"], manifest["to_version"]
    )
    for rel, (expected, size) in base.items():
        path = Path(app_root) / safe_relative(rel)
        if not path.is_file() or path.stat().st_size != size or _hash_file(path) != expected:
            raise UpdateError(f"No compatible delta: local runtime differs at {rel}.")


def _download(url: str, destination: Path, expected_sha: str) -> None:
    if not url.startswith(f"https://github.com/{REPO}/releases/download/"):
        raise UpdateError("Update ZIP is not hosted by the trusted release repository.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "FaceLoRA-Updates/1"})
    total = 0
    try:
        with urlopen(request, timeout=20) as response, tmp.open("wb") as out:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                total += len(chunk)
                if total > MAX_DELTA_BYTES:
                    raise UpdateError("Delta download exceeded the safety size limit.")
                out.write(chunk)
        if _hash_file(tmp) != expected_sha:
            raise UpdateError("Delta archive checksum mismatch.")
        os.replace(str(tmp), str(destination))
    finally:
        tmp.unlink(missing_ok=True)


def check_stable_release(app_root: Path, *, force: bool = False, now: Optional[float] = None) -> CheckResult:
    """Read published stable metadata ONLY; never download an update payload.

    Safe for default-on periodic checks. A user click is required before the
    separate check_and_prepare() method is called to download a delta.
    """
    root = Path(app_root).resolve()
    current = app_version(root)
    if not VERSION_RE.fullmatch(current):
        return CheckResult("development", current)
    _storage(root)  # Refuse system-drive update scratch.
    state_path = root / "_userdata" / "update_check.json"
    when = time.time() if now is None else now
    try:
        cached = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    try:
        last_checked = float(cached.get("last_checked", 0))
    except (ValueError, TypeError):
        last_checked = 0
    if not force and 0 <= when - last_checked < CHECK_INTERVAL_SECONDS:
        status = str(cached.get("status", "not_due"))
        if status in ("available", "current", "no_delta"):
            size = cached.get("download_bytes")
            size = size if type(size) is int and size >= 0 else None
            return CheckResult(status, current, str(cached.get("latest_tag", "")),
                               str(cached.get("release_url", "")), download_bytes=size)
        return CheckResult("not_due", current)
    release = latest_release()
    result = CheckResult("current", current, release.tag, release.page_url)
    if is_newer(release.tag, current):
        catalog_url = release.assets.get(CATALOG_ASSET)
        if not catalog_url:
            result = CheckResult("no_delta", current, release.tag, release.page_url)
        else:
            catalog = _read_json_response(catalog_url)
            if (not isinstance(catalog, dict) or catalog.get("schema") != 1 or
                catalog.get("release_version") != release.tag):
                raise UpdateError("Stable update catalog has an invalid version.")
            options = catalog.get("deltas")
            if not isinstance(options, list):
                raise UpdateError("Stable update catalog has invalid delta entries.")
            selection = next((
                item for item in options if isinstance(item, dict)
                and item.get("from_version") == current
                and item.get("to_version") == release.tag
                and item.get("asset") in release.assets
            ), None)
            if selection is None:
                result = CheckResult("no_delta", current, release.tag, release.page_url)
            else:
                # Display actual compressed update size when published, not a
                # fabricated comparison with the full Portable.
                size = selection.get("size_bytes")
                if type(size) is not int or not 0 <= size <= MAX_DELTA_BYTES:
                    size = None
                result = CheckResult("available", current, release.tag,
                                     release.page_url, download_bytes=size)
    _write_json(state_path, {
        "last_checked": when,
        "latest_tag": release.tag,
        "release_url": release.page_url,
        "status": result.status,
        "download_bytes": result.download_bytes,
    })
    return result


def check_and_prepare(app_root: Path, *, force: bool = False, now: Optional[float] = None) -> CheckResult:
    """Poll stable releases, stage only a compatible file delta, never full Portable.

    Safe to run off the GUI thread. Transient network errors are returned to
    the UI without affecting the dataset. The last check is throttled.
    """
    app_root = Path(app_root).resolve()
    current = app_version(app_root)
    if not VERSION_RE.fullmatch(current):
        return CheckResult("development", current)
    storage = _storage(app_root)
    state_file = app_root / "_userdata" / "update_check.json"
    pending = storage / "pending.json"
    if pending.is_file():
        try:
            saved = json.loads(pending.read_text(encoding="utf-8"))
            if (saved.get("from_version") == current and
                (storage / str(saved.get("archive_name", ""))).is_file()):
                return CheckResult("staged", current, str(saved["to_version"]), str(saved.get("release_url", "")))
        except (ValueError, OSError, TypeError, KeyError):
            pass
    timestamp = time.time() if now is None else now
    try:
        previous = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if not force and timestamp - float(previous.get("last_checked", 0)) < CHECK_INTERVAL_SECONDS:
        return CheckResult("not_due", current)
    release = latest_release()
    # Only a successful API response counts as a check.
    _write_json(state_file, {"last_checked": timestamp, "latest_tag": release.tag})
    if not is_newer(release.tag, current):
        return CheckResult("current", current, release.tag)
    catalog_url = release.assets.get(CATALOG_ASSET)
    if not catalog_url:
        return CheckResult("no_delta", current, release.tag, release.page_url)
    catalog = _read_json_response(catalog_url)
    if (not isinstance(catalog, dict) or catalog.get("schema") != 1 or
        catalog.get("release_version") != release.tag):
        raise UpdateError("Stable release update catalog is invalid.")
    options = catalog.get("deltas", [])
    if not isinstance(options, list):
        raise UpdateError("Stable release delta list is invalid.")
    selection = next((x for x in options if isinstance(x, dict) and
                      x.get("from_version") == current and x.get("to_version") == release.tag), None)
    if not selection:
        return CheckResult("no_delta", current, release.tag, release.page_url)
    asset_name = str(selection.get("asset", ""))
    delta_url = release.assets.get(asset_name)
    if not delta_url or not asset_name.lower().endswith(".zip"):
        raise UpdateError("Stable release does not contain the declared delta asset.")
    expected_sha = _require_hash(selection.get("sha256", ""))
    storage.mkdir(parents=True, exist_ok=True)
    zip_name = f"{current}-to-{release.tag}.zip"
    delta_path = storage / zip_name
    if not delta_path.is_file() or _hash_file(delta_path) != expected_sha:
        _download(delta_url, delta_path, expected_sha)
    manifest = validate_delta_file(delta_path, current, release.tag)
    _verify_local_base(app_root, manifest)
    _write_json(pending, {
        "schema": 1,
        "app_root": str(app_root),
        "from_version": current,
        "to_version": release.tag,
        "release_url": release.page_url,
        "archive_name": zip_name,
        "archive_sha256": expected_sha,
        "created_at": timestamp,
    })
    return CheckResult("staged", current, release.tag, release.page_url)


def launch_pending_update(app_root: Path, resource_root: Path, *, pid: Optional[int] = None) -> bool:
    """Dispatch bundled PowerShell helper after app quits; never run downloaded code."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    app_root = Path(app_root).resolve()
    storage = _storage(app_root)
    pending = storage / "pending.json"
    helper_source = Path(resource_root) / HELPER_RELATIVE
    if not pending.is_file() or not helper_source.is_file():
        return False
    try:
        data = json.loads(pending.read_text(encoding="utf-8"))
        if data.get("app_root") != str(app_root):
            return False
        helper = storage / "apply-update.ps1"
        shutil.copy2(helper_source, helper)
        ps = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if not ps:
            raise UpdateError("PowerShell was not found.")
        subprocess.Popen(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(helper), "-AppRoot", str(app_root),
             "-Pending", str(pending), "-WaitPid", str(pid or os.getpid())],
            cwd=str(storage),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000200 | 0x00000008,
            close_fds=True,
        )
        return True
    except (OSError, ValueError, UpdateError):
        return False
