"""Transactional Source Organizer.

Moves active dataset image files into status roots while preserving provenance.
No image pixels are modified. Optional-feature state and sample identity remain
attached to the existing Photo objects.

The feature does not know Composite internals; archive/excluded directory names
are supplied by the application layer.
"""
from __future__ import annotations

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


def execute_plan(plan: OrganizerPlan, progress=None) -> OrganizerResult:
    progress = progress or (lambda _current, _total, _message: None)
    root = Path(plan.root).resolve()
    total_steps = max(1, len(plan.moves) * 2)
    step = 0
    txn_root = root.parent / (
        f".{root.name}_source_organizer_txn_{uuid.uuid4().hex}"
    )
    staged = []
    completed = []

    try:
        txn_root.mkdir(parents=True, exist_ok=False)

        # Phase 1: move every changing source out of the way. This makes swaps
        # and cycles safe and prevents accidental overwrite.
        for index, move in enumerate(plan.moves):
            if not move.source.exists():
                raise FileNotFoundError(
                    f"Organizer 执行前源文件消失：{move.source}"
                )
            staged_path = txn_root / f"{index:06d}{move.source.suffix}"
            shutil.move(str(move.source), str(staged_path))
            staged.append((move, staged_path))
            step += 1
            progress(step, total_steps, f"暂存：{move.source.name}")

        # Phase 2: materialize final destinations.
        for move, staged_path in staged:
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            if move.destination.exists():
                raise FileExistsError(
                    f"Organizer 目标在执行期间出现冲突：{move.destination}"
                )
            shutil.move(str(staged_path), str(move.destination))
            completed.append(move)
            step += 1
            progress(step, total_steps, f"整理：{move.destination.name}")

        # Only after every filesystem move succeeds do we mutate Photo paths
        # and persistent feature state.
        updates = getattr(plan, "_record_updates", [])
        by_source = {_key(move.source): move for move in plan.moves}
        for record, move, origin_rel, origin_source in updates:
            if move is not None:
                record.path = move.destination
            record.feature_state[FEATURE_KEY] = {
                "origin_relative_path": str(origin_rel),
                "origin_source": str(origin_source),
            }

        try:
            txn_root.rmdir()
        except OSError:
            pass
        return OrganizerResult(
            moved=len(plan.moves),
            unchanged=plan.unchanged,
            skipped=plan.skipped,
        )

    except Exception as original_error:
        rollback_errors = []

        # Completed destinations can form swaps/cycles. Stage them again before
        # restoring any original source path so rollback itself cannot collide.
        rollback_completed = []
        for index, move in enumerate(completed):
            try:
                if move.destination.exists():
                    rollback_path = txn_root / (
                        f"rollback_{index:06d}{move.destination.suffix}"
                    )
                    shutil.move(str(move.destination), str(rollback_path))
                    rollback_completed.append((move, rollback_path))
            except Exception as exc:
                rollback_errors.append(
                    f"回滚暂存失败 {move.destination}: {exc}"
                )

        for move, rollback_path in reversed(rollback_completed):
            try:
                if rollback_path.exists():
                    move.source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(rollback_path), str(move.source))
            except Exception as exc:
                rollback_errors.append(
                    f"{rollback_path} -> {move.source}: {exc}"
                )

        completed_keys = {_key(move.source) for move in completed}
        for move, staged_path in reversed(staged):
            if _key(move.source) in completed_keys:
                continue
            try:
                if staged_path.exists():
                    move.source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged_path), str(move.source))
            except Exception as exc:
                rollback_errors.append(
                    f"{staged_path} -> {move.source}: {exc}"
                )

        try:
            if txn_root.exists():
                shutil.rmtree(txn_root)
        except Exception as exc:
            rollback_errors.append(f"清理事务目录失败：{exc}")

        if rollback_errors:
            raise RuntimeError(
                f"Source Organizer 失败：{original_error}\n"
                "自动回滚也有失败项：\n"
                + "\n".join(rollback_errors)
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
    print("Source Organizer backend self-test OK")
