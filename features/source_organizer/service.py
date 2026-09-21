"""Transactional Source Organizer.

Moves active dataset image files into status roots while preserving provenance.
No image pixels are modified. Optional-feature state and sample identity remain
attached to the existing Photo objects.

The feature does not know Composite internals; archive/excluded directory names
are supplied by the application layer.
"""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path


FEATURE_KEY = "source_organizer"
STATUS_DIRS = ("推荐", "备选", "淘汰")


@dataclass(frozen=True)
class OrganizerMove:
    source: Path
    destination: Path
    status: str
    sample_id: str
    origin_relative_path: str
    origin_source: str


@dataclass
class OrganizerPlan:
    root: Path
    moves: list[OrganizerMove] = field(default_factory=list)
    unchanged: int = 0
    skipped: int = 0

    @property
    def total(self):
        return len(self.moves) + self.unchanged + self.skipped

    def counts_by_status(self):
        out = {name: 0 for name in STATUS_DIRS}
        for move in self.moves:
            out[move.status] = out.get(move.status, 0) + 1
        return out


@dataclass
class OrganizerResult:
    moved: int
    unchanged: int
    skipped: int


def _key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except Exception as exc:
        raise ValueError(f"文件不在数据集根目录内：{path}") from exc


def _is_excluded(path: Path, root: Path, excluded_dir_names) -> bool:
    rel = _relative(path, root)
    excluded = {str(name).casefold() for name in excluded_dir_names}
    return any(part.casefold() in excluded for part in rel.parts[:-1])


def _origin_state(record, root: Path):
    state = record.feature_state.get(FEATURE_KEY)
    if isinstance(state, dict) and state.get("origin_relative_path"):
        rel = Path(str(state["origin_relative_path"]))
        origin_source = str(state.get("origin_source") or record.source)
        return rel, origin_source

    rel = _relative(record.path, root)
    # Organizer status directories are reserved roots. If the dataset was
    # already organized before this version, avoid status/status nesting.
    if len(rel.parts) > 1 and rel.parts[0] in STATUS_DIRS:
        rel = Path(*rel.parts[1:])
    return rel, str(record.source)


def build_plan(root: Path, records, excluded_dir_names=()) -> OrganizerPlan:
    root = Path(root).resolve()
    plan = OrganizerPlan(root=root)
    seen_destinations = {}
    move_sources = set()

    preliminary = []
    for record in records:
        source = Path(record.path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"源文件不存在：{source}")
        if _is_excluded(source, root, excluded_dir_names):
            plan.skipped += 1
            continue
        if record.status not in STATUS_DIRS:
            plan.skipped += 1
            continue

        origin_rel, origin_source = _origin_state(record, root)
        if origin_rel.is_absolute() or ".." in origin_rel.parts:
            raise ValueError(
                f"非法 Organizer 原始相对路径：{origin_rel}"
            )
        destination = (root / record.status / origin_rel).resolve()
        try:
            destination.relative_to(root)
        except Exception as exc:
            raise ValueError(
                f"Organizer 目标越界：{destination}"
            ) from exc

        if _key(source) == _key(destination):
            plan.unchanged += 1
            # Ensure legacy already-organized items gain stable provenance when
            # execution succeeds even though they do not move.
            preliminary.append(
                (record, None, origin_rel, origin_source)
            )
            continue

        move = OrganizerMove(
            source=source,
            destination=destination,
            status=record.status,
            sample_id=str(record.sample_id or ""),
            origin_relative_path=str(origin_rel),
            origin_source=origin_source,
        )
        preliminary.append((record, move, origin_rel, origin_source))
        move_sources.add(_key(source))

        dkey = _key(destination)
        previous = seen_destinations.get(dkey)
        if previous is not None:
            raise ValueError(
                "Organizer 目标冲突：\n"
                f"  {previous.source}\n"
                f"  {source}\n"
                f"都会移动到：{destination}"
            )
        seen_destinations[dkey] = move

    # Existing destinations are only safe when that file itself is part of the
    # same move plan and will first be staged out. This also supports status
    # swaps without overwrite.
    for _record, move, _origin_rel, _origin_source in preliminary:
        if move is None:
            continue
        if move.destination.exists() and _key(move.destination) not in move_sources:
            raise FileExistsError(
                f"Organizer 目标已存在且不会被本事务移走：{move.destination}"
            )

    plan.moves = [
        move for _record, move, _origin_rel, _origin_source in preliminary
        if move is not None
    ]
    # Keep ephemeral record linkage only on the plan object; it is not part of
    # the public serialized contract.
    plan._record_updates = preliminary
    return plan


def _write_manifest(path: Path, payload: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def _transaction_manifest(plan: OrganizerPlan, txn_root: Path):
    return {
        "version": 1,
        "root": str(Path(plan.root).resolve()),
        "moves": [
            {
                "source": str(move.source.resolve()),
                "destination": str(move.destination.resolve()),
                "stage": str((txn_root / f"{index:06d}{move.source.suffix}").resolve()),
                "state": "source",
            }
            for index, move in enumerate(plan.moves)
        ],
    }


def _recover_transaction(txn_root: Path):
    manifest_path = txn_root / "manifest.json"
    if not manifest_path.exists():
        # execute_plan writes the journal before moving any source. An empty
        # orphan transaction directory is therefore safe to discard.
        try:
            txn_root.rmdir()
            return
        except OSError as exc:
            raise RuntimeError(
                f"发现没有 journal 的 Source Organizer 事务目录：{txn_root}"
            ) from exc

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Source Organizer journal 无法读取：{manifest_path}"
        ) from exc

    moves = payload.get("moves")
    if not isinstance(moves, list):
        raise RuntimeError(f"Source Organizer journal 格式无效：{manifest_path}")

    recovery_root = txn_root / "_recovery"
    recovery_root.mkdir(exist_ok=True)
    restore_items = []
    errors = []

    # Extract every moved file to a neutral recovery location first. This is
    # required for path swaps/cycles.
    for index, item in enumerate(moves):
        try:
            source = Path(item["source"])
            destination = Path(item["destination"])
            stage = Path(item["stage"])
            state = str(item.get("state", "source"))
        except Exception as exc:
            errors.append(f"journal item {index}: {exc}")
            continue

        recovery = recovery_root / f"{index:06d}{source.suffix}"
        location = None
        already_source = False

        if state == "source":
            # Crash may happen after source->stage but before journal update.
            if stage.exists() and not source.exists():
                location = stage
            elif source.exists():
                already_source = True
            else:
                errors.append(f"找不到原文件或暂存文件：{source}")
        elif state == "staged":
            # Crash may happen after stage->destination but before journal update.
            if stage.exists():
                location = stage
            elif destination.exists():
                location = destination
            else:
                errors.append(f"找不到暂存或目标文件：{source}")
        elif state == "completed":
            if destination.exists():
                location = destination
            elif stage.exists():
                location = stage
            else:
                errors.append(f"找不到已完成事务文件：{source}")
        else:
            errors.append(f"未知 journal state {state!r}: {source}")

        if already_source:
            restore_items.append((source, None))
            continue
        if location is None:
            continue

        try:
            if recovery.exists():
                recovery.unlink()
            shutil.move(str(location), str(recovery))
            restore_items.append((source, recovery))
        except Exception as exc:
            errors.append(f"恢复暂存失败 {location}: {exc}")

    if errors:
        raise RuntimeError(
            "Source Organizer 自动恢复前置检查失败：\n" + "\n".join(errors)
        )

    # All moved contents are neutralized; original source paths can now be
    # restored without swap/cycle collisions.
    for source, recovery in restore_items:
        if recovery is None:
            continue
        try:
            source.parent.mkdir(parents=True, exist_ok=True)
            if source.exists():
                raise FileExistsError(f"原路径已被占用：{source}")
            shutil.move(str(recovery), str(source))
        except Exception as exc:
            errors.append(f"恢复原路径失败 {source}: {exc}")

    if errors:
        raise RuntimeError(
            "Source Organizer 自动恢复失败：\n" + "\n".join(errors)
        )

    try:
        shutil.rmtree(txn_root)
    except Exception as exc:
        raise RuntimeError(
            f"Source Organizer 已恢复文件，但清理事务目录失败：{txn_root}: {exc}"
        ) from exc


def recover_incomplete_transactions(root: Path) -> int:
    root = Path(root).resolve()
    pattern = f".{root.name}_source_organizer_txn_*"
    recovered = 0
    for txn_root in sorted(root.parent.glob(pattern), key=lambda p: str(p).lower()):
        if not txn_root.is_dir():
            continue
        _recover_transaction(txn_root)
        recovered += 1
    return recovered


def execute_plan(plan: OrganizerPlan, progress=None) -> OrganizerResult:
    progress = progress or (lambda _current, _total, _message: None)
    root = Path(plan.root).resolve()
    total_steps = max(1, len(plan.moves) * 2)
    step = 0
    txn_root = root.parent / (
        f".{root.name}_source_organizer_txn_{uuid.uuid4().hex}"
    )
    manifest_path = txn_root / "manifest.json"

    try:
        txn_root.mkdir(parents=True, exist_ok=False)
        manifest = _transaction_manifest(plan, txn_root)
        _write_manifest(manifest_path, manifest)

        # Phase 1: move every changing source out of the way. This makes swaps
        # and cycles safe and prevents accidental overwrite.
        for index, move in enumerate(plan.moves):
            if not move.source.exists():
                raise FileNotFoundError(
                    f"Organizer 执行前源文件消失：{move.source}"
                )
            staged_path = Path(manifest["moves"][index]["stage"])
            shutil.move(str(move.source), str(staged_path))
            manifest["moves"][index]["state"] = "staged"
            _write_manifest(manifest_path, manifest)
            step += 1
            progress(step, total_steps, f"暂存：{move.source.name}")

        # Phase 2: materialize final destinations.
        for index, move in enumerate(plan.moves):
            staged_path = Path(manifest["moves"][index]["stage"])
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            if move.destination.exists():
                raise FileExistsError(
                    f"Organizer 目标在执行期间出现冲突：{move.destination}"
                )
            shutil.move(str(staged_path), str(move.destination))
            manifest["moves"][index]["state"] = "completed"
            _write_manifest(manifest_path, manifest)
            step += 1
            progress(step, total_steps, f"整理：{move.destination.name}")

        # Only after every filesystem move succeeds do we mutate Photo paths
        # and persistent feature state.
        updates = getattr(plan, "_record_updates", [])
        for record, move, origin_rel, origin_source in updates:
            if move is not None:
                record.path = move.destination
            record.feature_state[FEATURE_KEY] = {
                "origin_relative_path": str(origin_rel),
                "origin_source": str(origin_source),
            }

        shutil.rmtree(txn_root)
        return OrganizerResult(
            moved=len(plan.moves),
            unchanged=plan.unchanged,
            skipped=plan.skipped,
        )

    except Exception as original_error:
        rollback_error = None
        try:
            if txn_root.exists():
                _recover_transaction(txn_root)
        except Exception as exc:
            rollback_error = exc

        if rollback_error is not None:
            raise RuntimeError(
                f"Source Organizer 失败：{original_error}\n"
                f"自动回滚也失败：{rollback_error}\n"
                f"事务目录保留在：{txn_root}"
            ) from original_error
        raise RuntimeError(
            f"Source Organizer 失败，已完整回滚：{original_error}"
        ) from original_error


def self_test():
    from tempfile import TemporaryDirectory

    from core.models import Photo

    with TemporaryDirectory() as td:
        root = Path(td) / "dataset"
        root.mkdir()
        archive = root / "_CompositeSplit_Originals"
        archive.mkdir()
        archived = archive / "old.jpg"
        archived.write_bytes(b"archive")

        a_dir = root / "sourceA"
        a_dir.mkdir()
        a = a_dir / "a.jpg"
        a.write_bytes(b"A")

        b_dir = root / "sourceB"
        b_dir.mkdir()
        b = b_dir / "b.jpg"
        b.write_bytes(b"B")

        pa = Photo(a);pa.sample_id="a";pa.manual_status="推荐"
        pb = Photo(b);pb.sample_id="b";pb.manual_status="淘汰"

        plan = build_plan(
            root,
            [pa, pb],
            excluded_dir_names=("_CompositeSplit_Originals",),
        )
        if len(plan.moves) != 2:
            raise RuntimeError("Organizer plan count self-test failed.")

        result = execute_plan(plan)
        if result.moved != 2:
            raise RuntimeError("Organizer move count self-test failed.")
        if not pa.path.exists() or not pb.path.exists():
            raise RuntimeError("Organizer destination self-test failed.")
        if pa.path != root / "推荐" / "sourceA" / "a.jpg":
            raise RuntimeError(f"Organizer 推荐 path failed: {pa.path}")
        if pb.path != root / "淘汰" / "sourceB" / "b.jpg":
            raise RuntimeError(f"Organizer 淘汰 path failed: {pb.path}")
        if not archived.exists():
            raise RuntimeError("Organizer touched Composite archive.")
        if pa.source != str(a_dir.resolve()):
            raise RuntimeError("Organizer source provenance was not preserved.")

        # Rerun is idempotent.
        rerun = build_plan(
            root,
            [pa, pb],
            excluded_dir_names=("_CompositeSplit_Originals",),
        )
        if rerun.moves or rerun.unchanged != 2:
            raise RuntimeError("Organizer idempotence self-test failed.")

        # A later status change moves between roots while preserving provenance.
        pa.manual_status = "备选"
        changed = build_plan(
            root,
            [pa, pb],
            excluded_dir_names=("_CompositeSplit_Originals",),
        )
        execute_plan(changed)
        if pa.path != root / "备选" / "sourceA" / "a.jpg":
            raise RuntimeError("Organizer status-change self-test failed.")
        if pa.source != str(a_dir.resolve()):
            raise RuntimeError("Organizer provenance changed after rerun.")

    # True status-root swap: both files use the same stable origin path, so
    # each destination is the other file's current source path.
    with TemporaryDirectory() as td:
        root = Path(td) / "dataset"
        left = root / "推荐" / "same.jpg"
        right = root / "备选" / "same.jpg"
        left.parent.mkdir(parents=True)
        right.parent.mkdir(parents=True)
        left.write_bytes(b"left")
        right.write_bytes(b"right")

        pl = Photo(left);pl.sample_id="left";pl.manual_status="备选"
        pr = Photo(right);pr.sample_id="right";pr.manual_status="推荐"
        for record, origin_source in ((pl, "source-left"), (pr, "source-right")):
            record.feature_state[FEATURE_KEY] = {
                "origin_relative_path": "same.jpg",
                "origin_source": origin_source,
            }

        cycle = build_plan(root, [pl, pr])
        if len(cycle.moves) != 2:
            raise RuntimeError("Organizer true-cycle plan self-test failed.")
        execute_plan(cycle)
        if pl.path != root / "备选" / "same.jpg":
            raise RuntimeError("Organizer cycle destination A failed.")
        if pr.path != root / "推荐" / "same.jpg":
            raise RuntimeError("Organizer cycle destination B failed.")
        if pl.path.read_bytes() != b"left" or pr.path.read_bytes() != b"right":
            raise RuntimeError("Organizer cycle content identity failed.")

    # Force a failure after one final move and ensure rollback restores both
    # original paths/content without mutating Photo paths.
    with TemporaryDirectory() as td:
        root = Path(td) / "dataset"
        root.mkdir()
        one = root / "one.jpg";one.write_bytes(b"one")
        two = root / "two.jpg";two.write_bytes(b"two")
        p1 = Photo(one);p1.sample_id="one";p1.manual_status="推荐"
        p2 = Photo(two);p2.sample_id="two";p2.manual_status="备选"
        rollback_plan = build_plan(root,[p1,p2])
        raised = False
        final_seen = [0]
        def fail_progress(_n,_total,message):
            if message.startswith("整理："):
                final_seen[0] += 1
                if final_seen[0] == 1:
                    raise RuntimeError("intentional rollback test")
        try:
            execute_plan(rollback_plan,progress=fail_progress)
        except RuntimeError as exc:
            raised = True
            if "已完整回滚" not in str(exc):
                raise RuntimeError(f"Organizer rollback report failed: {exc}")
        if not raised:
            raise RuntimeError("Organizer rollback injection did not fail.")
        if not one.exists() or not two.exists():
            raise RuntimeError("Organizer rollback did not restore source paths.")
        if one.read_bytes()!=b"one" or two.read_bytes()!=b"two":
            raise RuntimeError("Organizer rollback did not restore source content.")
        if p1.path!=one or p2.path!=two:
            raise RuntimeError("Organizer rollback mutated Photo paths.")
    # Simulate a process crash with a persisted journal after one source was
    # staged. Recovery on the next app refresh must restore the original file.
    with TemporaryDirectory() as td:
        root = Path(td) / "dataset"
        root.mkdir()
        original = root / "crash.jpg"
        original.write_bytes(b"crash-safe")
        photo = Photo(original);photo.sample_id="crash";photo.manual_status="推荐"
        crash_plan = build_plan(root,[photo])
        txn_root = root.parent / f".{root.name}_source_organizer_txn_crash_test"
        txn_root.mkdir()
        manifest = _transaction_manifest(crash_plan, txn_root)
        _write_manifest(txn_root / "manifest.json", manifest)
        stage = Path(manifest["moves"][0]["stage"])
        shutil.move(str(original), str(stage))
        manifest["moves"][0]["state"] = "staged"
        _write_manifest(txn_root / "manifest.json", manifest)
        if original.exists() or not stage.exists():
            raise RuntimeError("Organizer crash setup self-test failed.")
        if recover_incomplete_transactions(root) != 1:
            raise RuntimeError("Organizer crash recovery count self-test failed.")
        if not original.exists() or original.read_bytes()!=b"crash-safe":
            raise RuntimeError("Organizer crash recovery content self-test failed.")

    print("Source Organizer backend self-test OK")
