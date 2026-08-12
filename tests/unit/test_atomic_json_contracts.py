from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from ai_agent_core import atomic_write_json


class AtomicJsonContractsTest(unittest.TestCase):
    def test_rejects_non_standard_json_without_replacing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "state.json"
            target.write_text('{"old":true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                atomic_write_json(target, {"value": math.nan})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"old": True})

    def test_rejects_non_standard_json_before_creating_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "not-created"
            with self.assertRaisesRegex(ValueError, "standard JSON"):
                atomic_write_json(parent / "state.json", {"value": object()})
            self.assertFalse(parent.exists())

    def test_target_and_prefix_contracts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "state.json"
            for operation in (
                lambda: atomic_write_json(str(target), {}),  # type: ignore[arg-type]
                lambda: atomic_write_json(target, {}, prefix="../escape"),
            ):
                with self.subTest(operation=operation), self.assertRaises(ValueError):
                    operation()


if __name__ == "__main__":
    unittest.main()
