from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ai_agent_discovery import SkillRegistry, SkillRegistryError


class SkillRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "builtin"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_skill(self, plugin: str, directory: str, skill_id: str, entry: str = "main.py") -> None:
        skill_dir = self.root / plugin / "skills" / directory
        skill_dir.mkdir(parents=True)
        (skill_dir / entry).write_text("def run():\n    return None\n", encoding="utf-8")
        (skill_dir / "manifest.yaml").write_text(
            f"skill_id: {skill_id}\nname: Writer\nversion: 1.0.0\nentry_point: {entry}\n",
            encoding="utf-8",
        )

    def test_scan_registers_valid_skill(self) -> None:
        self.write_skill("short_drama", "writer", "short_drama.writer")
        registry = SkillRegistry(self.root)
        skills = registry.scan()
        self.assertEqual(len(skills), 1)
        self.assertEqual(registry.get("short_drama.writer").plugin_id, "short_drama")

    def test_duplicate_skill_id_is_rejected(self) -> None:
        self.write_skill("plugin_a", "writer", "writer")
        self.write_skill("plugin_b", "writer", "writer")
        with self.assertRaisesRegex(SkillRegistryError, "duplicate"):
            SkillRegistry(self.root).scan()

    def test_missing_entry_point_is_rejected(self) -> None:
        self.write_skill("plugin_a", "writer", "writer")
        (self.root / "plugin_a/skills/writer/main.py").unlink()
        with self.assertRaisesRegex(SkillRegistryError, "entry_point"):
            SkillRegistry(self.root).scan()

    def test_anonymous_lookup_and_sensitive_metadata_are_rejected(self) -> None:
        registry=SkillRegistry(self.root)
        with self.assertRaisesRegex(SkillRegistryError,"required"):registry.get("")
        self.write_skill("plugin_a","writer","writer")
        manifest=self.root/"plugin_a/skills/writer/manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8")+"transport:\n  headers:\n    Authorization: Bearer plaintext\n",encoding="utf-8")
        with self.assertRaisesRegex(SkillRegistryError,"sensitive fields"):registry.scan()


if __name__ == "__main__":
    unittest.main()
