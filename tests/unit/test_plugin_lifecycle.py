from __future__ import annotations

import unittest

from ai_agent_discovery import PluginLifecycleError, PluginRegistry


class PluginRegistryTest(unittest.TestCase):
    def test_complete_enable_disable_uninstall_flow(self) -> None:
        registry = PluginRegistry()
        self.assertEqual(registry.discover("plugin-a", "1.0.0").status, "discovered")
        self.assertEqual(registry.transition("plugin-a", "validated").status, "validated")
        self.assertEqual(registry.transition("plugin-a", "installed").status, "installed")
        self.assertEqual(registry.transition("plugin-a", "enabled").status, "enabled")
        self.assertEqual(registry.transition("plugin-a", "disabled").status, "disabled")
        self.assertEqual(registry.transition("plugin-a", "uninstalled").status, "uninstalled")

    def test_validation_and_runtime_failures_are_supported(self) -> None:
        registry = PluginRegistry()
        registry.discover("plugin-a", "1.0.0")
        self.assertEqual(registry.transition("plugin-a", "failed").status, "failed")
        self.assertEqual(registry.transition("plugin-a", "disabled").status, "disabled")

    def test_skipping_validation_is_rejected(self) -> None:
        registry = PluginRegistry()
        registry.discover("plugin-a", "1.0.0")
        with self.assertRaisesRegex(PluginLifecycleError, "forbidden"):
            registry.transition("plugin-a", "installed")

    def test_uninstalled_plugin_cannot_be_restored(self) -> None:
        registry = PluginRegistry()
        registry.discover("plugin-a", "1.0.0")
        registry.transition("plugin-a", "validated")
        registry.transition("plugin-a", "installed")
        registry.transition("plugin-a", "uninstalled")
        with self.assertRaisesRegex(PluginLifecycleError, "forbidden"):
            registry.transition("plugin-a", "enabled")

    def test_upgrade_and_rollback_preserve_version_history(self) -> None:
        registry = PluginRegistry(); registry.discover("plugin-a", "1.0.0"); registry.transition("plugin-a", "validated"); registry.transition("plugin-a", "installed")
        self.assertEqual(registry.upgrade("plugin-a", "2.0.0").version, "2.0.0")
        self.assertEqual(registry.rollback("plugin-a").version, "1.0.0")


if __name__ == "__main__":
    unittest.main()
