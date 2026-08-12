from __future__ import annotations

import unittest

from ai_agent_adapters import ProductionExtensionError, ProductionExtensionRegistry


class ProductionExtensionContractTest(unittest.TestCase):
    def test_metadata_is_deeply_immutable_from_caller_mutation(self) -> None:
        metadata={"routing":{"regions":["local"]}}
        item=ProductionExtensionRegistry().register("storage","local",lambda:object(),metadata=metadata)
        metadata["routing"]["regions"][0]="forged"
        self.assertEqual(item.metadata["routing"]["regions"][0],"local")
    def test_registration_rejects_runtime_pseudo_controls(self) -> None:
        with self.assertRaisesRegex(ProductionExtensionError,"trusted builtin"):ProductionExtensionRegistry(trusted_builtin_providers={("point","")})
        registry=ProductionExtensionRegistry()
        for kwargs in ({"enabled":1},{"replace":1},{"activate":1},{"metadata":[]},{"metadata":{"required_methods":[1]}}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ProductionExtensionError):registry.register("storage","local",lambda:object(),**kwargs)
        for operation in (lambda:registry.register(1,"local",lambda:object()),lambda:registry.register("storage",1,lambda:object())):
            with self.subTest(operation=operation),self.assertRaises(ProductionExtensionError):operation()
        for metadata in ({"value":float("nan")},{"value":object()}):
            with self.subTest(metadata=metadata),self.assertRaisesRegex(ProductionExtensionError,"standard JSON"):registry.register("storage","local",lambda:object(),metadata=metadata)
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
        for call in (lambda:registry.get(1),lambda:registry.activate("storage.test",1),lambda:registry.create(1)):
            with self.subTest(call=call),self.assertRaisesRegex(ProductionExtensionError,"required"):call()

    def test_enable_rejects_runtime_pseudo_boolean(self) -> None:
        registry = ProductionExtensionRegistry()
        registry.register("storage.test", "local", lambda: object())
        with self.assertRaisesRegex(ProductionExtensionError, "enabled must be boolean"):
            registry.enable("storage.test", 1)  # type: ignore[arg-type]
        self.assertTrue(registry.get("storage.test", "local").enabled)


if __name__ == "__main__":
    unittest.main()
