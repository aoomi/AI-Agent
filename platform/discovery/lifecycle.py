"""Closed plugin lifecycle state machine."""

from __future__ import annotations

from dataclasses import dataclass, replace


TRANSITIONS = frozenset({
    ("discovered", "validated"), ("discovered", "failed"),
    ("validated", "installed"), ("validated", "failed"),
    ("installed", "enabled"), ("installed", "uninstalled"),
    ("enabled", "disabled"), ("enabled", "failed"),
    ("disabled", "enabled"), ("disabled", "uninstalled"),
    ("failed", "disabled"),
})


class PluginLifecycleError(ValueError):
    """Raised for duplicate plugins or forbidden lifecycle transitions."""


@dataclass(frozen=True, slots=True)
class PluginRecord:
    plugin_id: str
    version: str
    status: str = "discovered"

    def __post_init__(self) -> None:
        if not self.plugin_id.strip() or not self.version.strip():
            raise PluginLifecycleError("plugin_id and version are required")


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginRecord] = {}
        self._history: dict[str, list[PluginRecord]] = {}

    def discover(self, plugin_id: str, version: str) -> PluginRecord:
        if plugin_id in self._plugins:
            raise PluginLifecycleError("plugin already discovered")
        record = PluginRecord(plugin_id, version)
        self._plugins[plugin_id] = record
        self._history[plugin_id] = [record]
        return record

    def transition(self, plugin_id: str, target: str) -> PluginRecord:
        try:
            current = self._plugins[plugin_id]
        except KeyError as error:
            raise PluginLifecycleError("plugin is not discovered") from error
        if (current.status, target) not in TRANSITIONS:
            raise PluginLifecycleError("plugin lifecycle transition is forbidden")
        updated = replace(current, status=target)
        self._plugins[plugin_id] = updated
        self._history[plugin_id].append(updated)
        return updated

    def list(self) -> tuple[PluginRecord, ...]:
        return tuple(sorted(self._plugins.values(), key=lambda item: item.plugin_id))

    def upgrade(self, plugin_id: str, version: str) -> PluginRecord:
        current = self.get(plugin_id)
        if current.status not in {"installed", "disabled"} or not version.strip() or version == current.version:
            raise PluginLifecycleError("plugin upgrade is forbidden")
        updated = replace(current, version=version.strip(), status="installed")
        self._plugins[plugin_id] = updated; self._history[plugin_id].append(updated); return updated

    def rollback(self, plugin_id: str) -> PluginRecord:
        current = self.get(plugin_id)
        if current.status not in {"installed", "disabled"}: raise PluginLifecycleError("plugin rollback is forbidden")
        previous = next((item for item in reversed(self._history[plugin_id][:-1]) if item.version != current.version), None)
        if previous is None: raise PluginLifecycleError("plugin rollback version does not exist")
        updated = PluginRecord(plugin_id, previous.version, "installed")
        self._plugins[plugin_id] = updated; self._history[plugin_id].append(updated); return updated

    def get(self, plugin_id: str) -> PluginRecord:
        try:
            return self._plugins[plugin_id]
        except KeyError as error:
            raise PluginLifecycleError("plugin is not discovered") from error
