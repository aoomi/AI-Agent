from __future__ import annotations

import unittest

from ai_agent_discovery import PluginLifecycleError, PluginRegistry


class PluginRegistryTest(unittest.TestCase):
    def test_record_identity_version_and_status_contracts_are_rejected(self) -> None:
        registry=PluginRegistry()
        for plugin_id,version in (("../escape","1.0.0"),("plugin","1.0")):
            with self.subTest(plugin_id=plugin_id,version=version),self.assertRaises(PluginLifecycleError):registry.discover(plugin_id,version)
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

    def test_anonymous_plugin_controls_are_rejected_before_registry_access(self) -> None:
        registry=PluginRegistry()
        for operation in (
            lambda:registry.discover("", "1.0"), lambda:registry.discover("plugin", ""),
            lambda:registry.get(""), lambda:registry.transition("", "enabled"),
            lambda:registry.upgrade("", "2.0"), lambda:registry.rollback(""),
        ):
            with self.assertRaisesRegex(PluginLifecycleError, "required"):operation()

    def test_runtime_identity_types_are_rejected(self) -> None:
        registry=PluginRegistry()
        for operation in (lambda:registry.discover(1,"1.0.0"),lambda:registry.discover("plugin",1),lambda:registry.get(1),lambda:registry.transition(1,"enabled"),lambda:registry.upgrade(1,"2.0.0"),lambda:registry.rollback(1)):
            with self.subTest(operation=operation),self.assertRaises(PluginLifecycleError):operation()


if __name__ == "__main__":
    unittest.main()
