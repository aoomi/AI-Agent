"""Shared crash-safe JSON persistence primitive."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def atomic_write_json(target: Path, payload: Any, *, prefix: str = "atomic-json-") -> None:
    if not isinstance(target, Path):
        raise ValueError("atomic JSON target must be a Path")
    if not isinstance(prefix, str) or not prefix or "/" in prefix or "\x00" in prefix:
        raise ValueError("atomic JSON prefix is invalid")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("atomic JSON payload must be standard JSON") from error
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=prefix, suffix=".json", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
