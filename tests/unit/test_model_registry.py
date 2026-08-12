from __future__ import annotations

import unittest

from ai_agent_llm_gateway import (
    ModelDefinition,
    ModelRegistry,
    ModelRegistryError,
    ModelRequirements,
)


def model(model_id: str, capabilities: set[str], *, enabled: bool = True, context: int = 8192) -> ModelDefinition:
    return ModelDefinition.create(
        model_id=model_id,
        provider_id="provider-a",
        display_name=model_id,
        capabilities=capabilities,
        enabled=enabled,
        context_window=context,
    )


class ModelRegistryTest(unittest.TestCase):
    def test_registration_is_idempotent_and_conflicts_are_rejected(self) -> None:
        registry = ModelRegistry()
        definition = model("reasoner", {"chat", "reasoning"})
        self.assertFalse(registry.register(definition)[1])
        self.assertTrue(registry.register(definition)[1])
        with self.assertRaisesRegex(ModelRegistryError, "conflicting"):
            registry.register(model("reasoner", {"chat"}))

    def test_selection_enforces_enabled_capabilities_and_context(self) -> None:
        registry = ModelRegistry()
        registry.register(model("small", {"chat", "reasoning"}, context=8192))
        registry.register(model("large", {"chat", "reasoning", "tool_calling"}, context=32768))
        registry.register(model("disabled", {"chat", "reasoning", "tool_calling"}, enabled=False, context=16384))
        selected = registry.select(ModelRequirements(frozenset({"chat", "tool_calling"}), 12000))
        self.assertEqual(selected.model_id, "large")

    def test_preferred_model_must_satisfy_requirements(self) -> None:
        registry = ModelRegistry()
        registry.register(model("chat", {"chat"}))
        with self.assertRaisesRegex(ModelRegistryError, "does not satisfy"):
            registry.select(ModelRequirements(frozenset({"reasoning"})), preferred_model_id="chat")

    def test_absent_real_model_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(ModelRegistryError, "no enabled model"):
            ModelRegistry().select(ModelRequirements(frozenset({"chat"})))

    def test_invalid_definition_is_rejected(self) -> None:
        with self.assertRaisesRegex(ModelRegistryError, "invalid model capabilities"):
            model("invalid", {"audio"})
        with self.assertRaisesRegex(ModelRegistryError, "secrets"):
            ModelDefinition.create(model_id="m", provider_id="p", display_name="M", capabilities={"chat"}, context_window=8, settings={"transport":{"headers":[{"authorization":"Bearer hidden"}]}})

    def test_anonymous_model_controls_and_empty_requirements_are_rejected(self) -> None:
        registry=ModelRegistry();registry.register(model("chat",{"chat"}))
        for operation in (
            lambda:registry.get(""), lambda:registry.set_enabled("chat",1),
            lambda:registry.select(ModelRequirements(frozenset())),
            lambda:registry.select(ModelRequirements(frozenset({"chat"})),preferred_model_id=" "),
        ):
            with self.assertRaises(ModelRegistryError):operation()

    def test_runtime_model_requirement_and_control_types_are_rejected(self) -> None:
        for build in (lambda:ModelDefinition.create(model_id=1,provider_id="p",display_name="M",capabilities={"chat"},context_window=8),lambda:ModelDefinition.create(model_id="m",provider_id="p",display_name="M",capabilities={"chat"},context_window=8,settings=[]),lambda:ModelRequirements({"chat"})):
            with self.subTest(build=build),self.assertRaises(ModelRegistryError):build()
        registry=ModelRegistry();registry.register(model("chat",{"chat"}))
        for operation in (lambda:registry.register(object()),lambda:registry.get(1),lambda:registry.get("chat",require_enabled=1),lambda:registry.list(enabled_only=1),lambda:registry.select(object()),lambda:registry.select(ModelRequirements(frozenset({"chat"})),preferred_model_id=1)):
            with self.subTest(operation=operation),self.assertRaises(ModelRegistryError):operation()


if __name__ == "__main__":
    unittest.main()
