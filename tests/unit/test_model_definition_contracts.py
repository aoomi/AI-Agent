from __future__ import annotations

import unittest

from ai_agent_llm_gateway import ModelDefinition, ModelRegistryError, ModelRequirements


class ModelDefinitionContractTest(unittest.TestCase):
    def _create(self, **changes):
        values=dict(model_id="model",provider_id="provider",display_name="Model",capabilities=("chat",),
                    enabled=True,context_window=1024)
        values.update(changes); return ModelDefinition.create(**values)

    def test_definition_rejects_ambiguous_runtime_types(self) -> None:
        for changes in ({"capabilities":"chat"},{"capabilities":("chat",1)},{"enabled":1},{"context_window":True}):
            with self.subTest(changes=changes),self.assertRaises(ModelRegistryError):self._create(**changes)

    def test_requirements_reject_empty_scope_and_pseudo_integer(self) -> None:
        for build in (
            lambda: ModelRequirements(frozenset()),
            lambda: ModelRequirements(frozenset({"chat"}),minimum_context_window=True),
            lambda: ModelRequirements(frozenset({"chat"}),provider_id=" "),
        ):
            with self.subTest(build=build),self.assertRaises(ModelRegistryError):build()

    def test_settings_reject_non_standard_json(self) -> None:
        for settings in ({"value":float("nan")},{"value":object()}):
            with self.subTest(settings=settings),self.assertRaisesRegex(ModelRegistryError,"standard JSON"):
                self._create(settings=settings)

    def test_settings_are_deeply_immutable_from_caller_mutation(self) -> None:
        settings={"routing":{"regions":["local"]}}
        model=self._create(settings=settings)
        settings["routing"]["regions"][0]="forged"
        self.assertEqual(model.settings["routing"]["regions"][0],"local")


if __name__=="__main__":unittest.main()
