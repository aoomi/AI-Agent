from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_document_status_gate_is_part_of_repository_contract() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/maintenance/check_document_status.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "document status check passed"
