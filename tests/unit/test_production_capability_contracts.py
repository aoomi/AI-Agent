from __future__ import annotations

import unittest

from ai_agent_adapters import ProductionCapabilityError, ProductionCapabilityRegistry


class ProductionCapabilityContractTest(unittest.TestCase):
    def test_metadata_is_deeply_immutable_from_caller_mutation(self) -> None:
        metadata={"routing":{"regions":["local"]}}
        item=ProductionCapabilityRegistry().register("video","local",lambda:1,metadata=metadata)
        metadata["routing"]["regions"][0]="forged"
        self.assertEqual(item.metadata["routing"]["regions"][0],"local")
    def test_handler_cannot_mutate_nested_caller_inputs(self) -> None:
        def handler(**inputs):inputs["routing"]["regions"][0]="handler";return {"ok":True}
        inputs={"routing":{"regions":["local"]}};ProductionCapabilityRegistry().register("video","local",handler)
        registry=ProductionCapabilityRegistry();registry.register("video","local",handler);registry.invoke("video",**inputs)
        self.assertEqual(inputs["routing"]["regions"][0],"local")
    def test_failed_provider_cannot_mutate_fallback_inputs(self) -> None:
        registry=ProductionCapabilityRegistry();seen=[]
        def failed(**inputs):inputs["routing"]["regions"][0]="failed";raise RuntimeError("failed")
        def backup(**inputs):seen.append(inputs["routing"]["regions"][0]);return {"ok":True}
        registry.register("video","a",failed,priority=1);registry.register("video","b",backup,priority=1)
        registry.invoke("video",allow_fallback=True,routing={"regions":["local"]})
        self.assertEqual(seen,["local"])
    def test_registration_rejects_runtime_pseudo_controls(self) -> None:
        registry=ProductionCapabilityRegistry()
        for kwargs in ({"enabled":1},{"healthy":0},{"replace":1},{"priority":True},{"metadata":[]}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ProductionCapabilityError):registry.register("video","local",lambda:1,**kwargs)
        for operation in (lambda:registry.register(1,"local",lambda:1),lambda:registry.register_once("video",1,lambda:1)):
            with self.subTest(operation=operation),self.assertRaises(ProductionCapabilityError):operation()
        for metadata in ({"value":float("nan")},{"value":object()}):
            with self.subTest(metadata=metadata),self.assertRaisesRegex(ProductionCapabilityError,"standard JSON"):registry.register("video","local",lambda:1,metadata=metadata)
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
        for call in (lambda:registry.get(1),lambda:registry.invoke(1),lambda:registry.health("video.generate",1,True)):
            with self.subTest(call=call),self.assertRaisesRegex(ProductionCapabilityError,"required"):call()

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
