from __future__ import annotations

import unittest

from ai_agent_adapters import ProductionExtensionError, ProductionExtensionRegistry


class ProductionExtensionContractTest(unittest.TestCase):
    def test_controls_reject_empty_identifiers(self) -> None:
        registry = ProductionExtensionRegistry()
        registry.register("storage.test", "local", lambda: object())
        calls = (
            lambda: registry.unregister(" "), lambda: registry.unregister("storage.test", " "),
            lambda: registry.enable(" ", True), lambda: registry.has(" "),
            lambda: registry.get(" "), lambda: registry.activate("storage.test", " "),
            lambda: registry.create(" "), lambda: registry.create("storage.test", provider_id=" "),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(ProductionExtensionError, "required"):
                call()

    def test_enable_rejects_runtime_pseudo_boolean(self) -> None:
        registry = ProductionExtensionRegistry()
        registry.register("storage.test", "local", lambda: object())
        with self.assertRaisesRegex(ProductionExtensionError, "enabled must be boolean"):
            registry.enable("storage.test", 1)  # type: ignore[arg-type]
        self.assertTrue(registry.get("storage.test", "local").enabled)


if __name__ == "__main__":
    unittest.main()
