from __future__ import annotations

import unittest

from ai_agent_adapters import ProductionCapabilityError, ProductionCapabilityRegistry


class ProductionCapabilityContractTest(unittest.TestCase):
    def test_registration_rejects_runtime_pseudo_controls(self) -> None:
        registry=ProductionCapabilityRegistry()
        for kwargs in ({"enabled":1},{"healthy":0},{"replace":1},{"priority":True},{"metadata":[]}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ProductionCapabilityError):registry.register("video","local",lambda:1,**kwargs)
    def test_controls_reject_empty_identifiers(self) -> None:
        registry = ProductionCapabilityRegistry()
        registry.register("video.generate", "local", lambda: {"ok": True})
        calls = (
            lambda: registry.unregister(" "), lambda: registry.unregister("video.generate", " "),
            lambda: registry.has(" "), lambda: registry.get(" "),
            lambda: registry.enable(" ", True), lambda: registry.health("video.generate", " ", True),
            lambda: registry.invoke(" "), lambda: registry.invoke("video.generate", provider_id=" "),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(ProductionCapabilityError, "required"):
                call()

    def test_runtime_boolean_controls_are_strict(self) -> None:
        registry = ProductionCapabilityRegistry()
        registry.register("video.generate", "local", lambda: {"ok": True})
        with self.assertRaisesRegex(ProductionCapabilityError, "enabled must be boolean"):
            registry.enable("video.generate", 1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ProductionCapabilityError, "healthy must be boolean"):
            registry.health("video.generate", "local", 0)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ProductionCapabilityError, "allow_fallback must be boolean"):
            registry.invoke("video.generate", allow_fallback=1)  # type: ignore[arg-type]
        self.assertTrue(registry.get("video.generate", "local").enabled)
        self.assertTrue(registry.get("video.generate", "local").healthy)


if __name__ == "__main__":
    unittest.main()
