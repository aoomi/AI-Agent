#!/usr/bin/env python3
"""Create and restore verifiable single-node backups."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


BACKUP_ROOTS = ("config", "database", "assets", "audit", "checkpoints")
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sqlite(path: Path) -> bool:
    if path.suffix.lower() not in SQLITE_SUFFIXES:
        return False
    with path.open("rb") as stream:
        return stream.read(16) == b"SQLite format 3\x00"


def _snapshot_file(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise SystemExit(f"UNSAFE_BACKUP_SOURCE_ENTRY:{source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if _is_sqlite(source):
        source_uri = f"{source.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as origin, sqlite3.connect(target) as snapshot:
            origin.backup(snapshot)
        shutil.copystat(source, target, follow_symlinks=False)
        return
    shutil.copy2(source, target)


def _snapshot_tree(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise SystemExit(f"UNSAFE_BACKUP_SOURCE_ENTRY:{source.name}")
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir(), key=lambda item: item.name):
        if any(entry.name.endswith(suffix) for suffix in ("-wal", "-shm", "-journal")):
            base = entry.with_name(entry.name.rsplit("-", 1)[0])
            if base.is_file() and _is_sqlite(base):
                continue
        if entry.is_symlink():
            raise SystemExit(f"UNSAFE_BACKUP_SOURCE_ENTRY:{entry.name}")
        destination = target / entry.name
        if entry.is_dir():
            _snapshot_tree(entry, destination)
        elif entry.is_file():
            _snapshot_file(entry, destination)
        else:
            raise SystemExit(f"UNSAFE_BACKUP_SOURCE_ENTRY:{entry.name}")
    shutil.copystat(source, target, follow_symlinks=False)


def _inventory(root: Path) -> list[dict[str, object]]:
    return [
        {"path":path.relative_to(root).as_posix(), "size":path.stat().st_size, "sha256":_file_sha256(path), "mode":stat.S_IMODE(path.stat().st_mode)}
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item:item.as_posix())
    ]


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def backup(source: Path, output: Path) -> dict[str, object]:
    if source.is_symlink() or output.is_symlink():
        raise SystemExit("INVALID_BACKUP_SOURCE")
    source, output = source.resolve(), output.resolve()
    if not source.is_dir() or source == Path("/") or output == source or source in output.parents:
        raise SystemExit("INVALID_BACKUP_SOURCE")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="backup-snapshot-", dir=output.parent) as temporary_dir:
        snapshot_root = Path(temporary_dir) / "snapshot"
        snapshot_root.mkdir()
        for name in BACKUP_ROOTS:
            path = source / name
            if path.exists() or path.is_symlink():
                _snapshot_tree(path, snapshot_root / name)
        inventory = _inventory(snapshot_root)
        descriptor, archive_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
        os.close(descriptor)
        temporary_archive = Path(archive_name)
        try:
            with tarfile.open(temporary_archive, "w:gz") as archive:
                for name in BACKUP_ROOTS:
                    path = snapshot_root / name
                    if path.exists():
                        archive.add(path, arcname=name, recursive=True)
            with temporary_archive.open("rb") as stream:
                os.fsync(stream.fileno())
            archive_digest = _file_sha256(temporary_archive)
            os.replace(temporary_archive, output)
            _fsync_directory(output.parent)
        finally:
            temporary_archive.unlink(missing_ok=True)
    manifest: dict[str, object] = {
        "version": 2,
        "archive": output.name,
        "sha256": archive_digest,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": inventory,
    }
    _atomic_json(output.with_suffix(output.suffix + ".manifest.json"), manifest)
    return manifest


def _safe_member(member: tarfile.TarInfo, target: Path, seen: set[str]) -> Path:
    normalized = Path(member.name)
    if member.name in seen or normalized.is_absolute() or ".." in normalized.parts:
        raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
    if not normalized.parts or normalized.parts[0] not in BACKUP_ROOTS:
        raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
    if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
        raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
    resolved = (target / normalized).resolve()
    if not resolved.is_relative_to(target):
        raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
    seen.add(member.name)
    return resolved


def _extract_verified(archive: Path, target: Path, expected_files: list[dict[str, object]]) -> None:
    seen: set[str] = set()
    directory_modes: list[tuple[Path, int]] = []
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            destination = _safe_member(member, target, seen)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                directory_modes.append((destination, member.mode & 0o777))
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = package.extractfile(member)
            if source is None:
                raise SystemExit("UNSAFE_BACKUP_ARCHIVE")
            with source, destination.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            os.chmod(destination, member.mode & 0o777)
    for directory, mode in reversed(directory_modes):
        os.chmod(directory, mode)
    actual = _inventory(target)
    if actual != expected_files:
        raise SystemExit("RESTORED_CONTENT_MISMATCH")


def restore(archive: Path, target: Path, manifest: Path) -> None:
    if archive.is_symlink() or target.is_symlink() or manifest.is_symlink():
        raise SystemExit("UNSAFE_RESTORE_PATH")
    archive, target, manifest = archive.resolve(), target.resolve(), manifest.resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("version") != 2 or payload.get("archive") != archive.name or not isinstance(payload.get("files"), list):
        raise SystemExit("INVALID_BACKUP_MANIFEST")
    if _file_sha256(archive) != payload.get("sha256"):
        raise SystemExit("BACKUP_CHECKSUM_MISMATCH")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise SystemExit("RESTORE_TARGET_NOT_EMPTY")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent))
    try:
        _extract_verified(archive, temporary, payload["files"])
        if target.exists():
            target.rmdir()
        os.replace(temporary, target)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("backup")
    create.add_argument("source", type=Path)
    create.add_argument("output", type=Path)
    recover = commands.add_parser("restore")
    recover.add_argument("archive", type=Path)
    recover.add_argument("target", type=Path)
    recover.add_argument("manifest", type=Path)
    arguments = parser.parse_args()
    backup(arguments.source, arguments.output) if arguments.action == "backup" else restore(arguments.archive, arguments.target, arguments.manifest)


if __name__ == "__main__":
    main()
