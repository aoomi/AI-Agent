from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_core import AgentContextError, AgentContextStore, AgentScheduler, ExecutionResult
from ai_agent_discovery import AgentRegistry, SkillDefinition


def skill(skill_id: str, name: str) -> SkillDefinition:
    return SkillDefinition(skill_id, name, "1", "main.py", "short_drama", Path("manifest.yaml"), {})


class AgentPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.writer = self.registry.register(skill("writer", "Writer"))[0]
        self.director = self.registry.register(skill("director", "Director"))[0]
        self.contexts = AgentContextStore()
        self.scheduler = AgentScheduler(self.registry, self.contexts)

    def test_upstream_completion_automatically_runs_downstream(self) -> None:
        calls: list[str] = []
        self.scheduler.add_executor(self.writer.agent_id, lambda context: (calls.append("writer") or ExecutionResult("completed", {"script": "v1"})))
        self.scheduler.add_executor(self.director.agent_id, lambda context: (calls.append("director") or ExecutionResult("completed", {"shots": context.values["upstream"]["script"]})))
        run = self.scheduler.start("tenant-a", "project-a", (self.writer.agent_id, self.director.agent_id), {"brief": "story"})
        self.assertEqual(run.status, "completed")
        self.assertEqual(calls, ["writer", "director"])
        self.assertEqual(self.contexts.get("tenant-a", "project-a", self.director.agent_id).values["shots"], "v1")

    def test_waiting_human_can_resume(self) -> None:
        def writer(context):
            if not context.values.get("approved"):
                return ExecutionResult("waiting_human", {"draft": "v1"})
            return ExecutionResult("completed", {"script": "approved"})
        self.scheduler.add_executor(self.writer.agent_id, writer)
        run = self.scheduler.start("tenant-a", "project-a", (self.writer.agent_id,), {})
        self.assertEqual(run.status, "waiting_human")
        self.assertEqual(self.scheduler.resume(run.run_id, {"approved": True}).status, "completed")

    def test_context_isolation_blocks_cross_project_and_agent_reads(self) -> None:
        self.contexts.create("tenant-a", "project-a", self.writer.agent_id)
        with self.assertRaises(AgentContextError):
            self.contexts.get("tenant-a", "project-b", self.writer.agent_id)
        with self.assertRaises(AgentContextError):
            self.contexts.get("tenant-a", "project-a", self.director.agent_id)


if __name__ == "__main__": unittest.main()
