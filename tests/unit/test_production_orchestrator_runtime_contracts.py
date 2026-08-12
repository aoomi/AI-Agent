from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plugins.builtin.short_drama.workflows.production_orchestrator import ProductionOrchestrator


IDENTITY={"tenant_id":"t","user_id":"u","project_id":"p"}


class ProductionOrchestratorRuntimeContractsTest(unittest.TestCase):
    def test_runtime_controls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain=ProductionOrchestrator(Path(directory)/"graph.sqlite")
            for operation in (
                lambda:brain.register_stage("video",lambda _: {},provider_id=1),lambda:brain.register_stage("video",lambda _: {},enabled=1),
                lambda:brain.enable_stage("video",1),lambda:brain.execute(IDENTITY,"video",[]),
                lambda:brain.begin(IDENTITY,"requirements",stage_generation=True),lambda:brain.state([]),
                lambda:brain.state({"tenant_id":1,"user_id":"u","project_id":"p"}),lambda:brain.report(IDENTITY,"requirements",1),
                lambda:brain.report(IDENTITY,"requirements","running",trusted=1),
            ):
                with self.subTest(operation=operation),self.assertRaises(ValueError):operation()

    def test_event_fences_require_exact_non_negative_integers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain=ProductionOrchestrator(Path(directory)/"graph.sqlite")
            for evidence in ({"projection_revision":True},{"projection_revision":-1},{"stage_generation":True},{"stage_generation":-1}):
                with self.subTest(evidence=evidence),self.assertRaises(ValueError):brain.report(IDENTITY,"requirements","running",**evidence)

    def test_retry_receives_pristine_nested_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain=ProductionOrchestrator(Path(directory)/"graph.sqlite")
            seen=[]
            def executor(inputs):
                seen.append(inputs["routing"]["regions"][0])
                if len(seen)==1:
                    inputs["routing"]["regions"][0]="mutated"
                    raise ConnectionError("retry")
                return {"ok":True}
            brain.register_stage("requirements",executor)
            original={"routing":{"regions":["local"]}}
            result=brain.execute(IDENTITY,"requirements",original)
            self.assertEqual(seen,["local","local"])
            self.assertEqual(original,{"routing":{"regions":["local"]}})
            self.assertEqual(result["output"],{"ok":True})

    def test_executor_output_is_snapshotted_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain=ProductionOrchestrator(Path(directory)/"graph.sqlite")
            original={"routing":{"regions":["local"]}}
            brain.register_stage("requirements",lambda _:original)
            result=brain.execute(IDENTITY,"requirements",{})
            original["routing"]["regions"][0]="mutated"
            self.assertEqual(result["output"],{"routing":{"regions":["local"]}})
            self.assertEqual(
                brain.state(IDENTITY)["stage_events"]["requirements"]["evidence"],
                {"routing":{"regions":["local"]}},
            )


if __name__ == "__main__":unittest.main()
