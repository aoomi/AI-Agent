"""Discover and validate Skill manifests from installed plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml


class SkillRegistryError(ValueError):
    """Raised when Skill discovery finds an invalid or duplicate manifest."""


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    name: str
    version: str
    entry_point: str
    plugin_id: str
    manifest_path: Path
    metadata: Mapping[str, Any]


class SkillRegistry:
    def __init__(self, builtin_plugins_root: Path) -> None:
        self._root = builtin_plugins_root.resolve()
        self._skills: dict[str, SkillDefinition] = {}

    def scan(self) -> tuple[SkillDefinition, ...]:
        discovered: dict[str, SkillDefinition] = {}
        for manifest_path in sorted(self._root.glob("*/skills/*/manifest.yaml")):
            definition = self._load_manifest(manifest_path)
            if definition.skill_id in discovered:
                raise SkillRegistryError(f"duplicate skill_id: {definition.skill_id}")
            discovered[definition.skill_id] = definition
        self._skills = discovered
        return tuple(discovered.values())

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            return self._skills[skill_id]
        except KeyError as error:
            raise SkillRegistryError(f"unknown skill_id: {skill_id}") from error

    def all(self) -> tuple[SkillDefinition, ...]:
        return tuple(self._skills.values())

    def _load_manifest(self, manifest_path: Path) -> SkillDefinition:
        resolved = manifest_path.resolve()
        if not resolved.is_relative_to(self._root):
            raise SkillRegistryError("manifest escapes plugin root")
        try:
            raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise SkillRegistryError(f"cannot read manifest: {resolved}") from error
        if not isinstance(raw, dict):
            raise SkillRegistryError("manifest must be an object")
        values = {}
        for field in ("skill_id", "name", "version", "entry_point"):
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SkillRegistryError(f"manifest field {field} is required")
            values[field] = value.strip()
        entry_path = (resolved.parent / values["entry_point"]).resolve()
        if not entry_path.is_relative_to(resolved.parent) or not entry_path.is_file():
            raise SkillRegistryError("entry_point must reference a file inside the Skill directory")
        plugin_id = resolved.parents[2].name
        metadata = {key: value for key, value in raw.items() if key not in values}
        return SkillDefinition(
            **values,
            plugin_id=plugin_id,
            manifest_path=resolved,
            metadata=MappingProxyType(metadata),
        )
