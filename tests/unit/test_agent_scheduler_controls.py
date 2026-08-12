from __future__ import annotations

import unittest
import threading
from pathlib import Path

from ai_agent_core import AgentContextStore, AgentScheduler, ExecutionResult, SchedulerError, RemediationInstruction
from ai_agent_discovery import AgentRegistry, SkillDefinition


def skill(skill_id: str) -> SkillDefinition:
    return SkillDefinition(skill_id, skill_id, "1", "main.py", "test", Path("manifest.yaml"), {})


class AgentSchedulerControlsTest(unittest.TestCase):
    def test_executor_result_is_deeply_snapshotted(self):
        values={"state":{"steps":["completed"]}}
        self.scheduler.add_executor(self.first.agent_id,lambda _context:ExecutionResult("completed",values))
        run=self.scheduler.start("tenant","project",(self.first.agent_id,),{},auto_run=False);self.scheduler.run(run.run_id)
        values["state"]["steps"][0]="forged"
        self.assertEqual(self.scheduler.contexts.get("tenant","project",self.first.agent_id).values["state"]["steps"][0],"completed")
    def test_runtime_dependency_and_resume_contracts_are_rejected(self) -> None:
        with self.assertRaisesRegex(SchedulerError,"registry contract"):AgentScheduler(object(),AgentContextStore())
        with self.assertRaisesRegex(SchedulerError,"context contract"):AgentScheduler(AgentRegistry(),object())
        with self.assertRaisesRegex(SchedulerError,"run_id"):self.scheduler.run(" ")
        for operation in (lambda:self.scheduler.run(1),lambda:self.scheduler.remediation(1),lambda:self.scheduler.schedule_remediation(object()),lambda:self.scheduler.start(1,"project",(self.first.agent_id,),{},auto_run=False),lambda:self.scheduler.start("tenant","project",[self.first.agent_id],{},auto_run=False)):
            with self.subTest(operation=operation),self.assertRaises(SchedulerError):operation()
    def setUp(self) -> None:
        registry = AgentRegistry(); self.first = registry.register(skill("first"))[0]; self.second = registry.register(skill("second"))[0]
        self.scheduler = AgentScheduler(registry, AgentContextStore())

    def test_parallel_run_completes_all_agents(self) -> None:
        calls = []
        self.scheduler.add_executor(self.first.agent_id, lambda context: (calls.append("first") or ExecutionResult("completed", {"one": 1})))
        self.scheduler.add_executor(self.second.agent_id, lambda context: (calls.append("second") or ExecutionResult("completed", {"two": 2})))
        run = self.scheduler.start("tenant", "project", (self.first.agent_id, self.second.agent_id), {"shared": True}, mode="parallel")
        self.assertEqual(run.status, "completed")
        self.assertEqual(set(calls), {"first", "second"})

    def test_pause_resume_retry_and_manual_takeover(self) -> None:
        attempts = []
        def execute(context):
            attempts.append(1)
            return ExecutionResult("failed" if len(attempts) == 1 else "completed", {})
        self.scheduler.add_executor(self.first.agent_id, execute)
        run = self.scheduler.start("tenant", "project", (self.first.agent_id,), {}, auto_run=False, max_retries=1)
        self.assertEqual(self.scheduler.pause(run.run_id).status, "paused")
        failed = self.scheduler.resume(run.run_id, {})
        self.assertEqual(failed.status, "failed")
        self.assertEqual(self.scheduler.retry(run.run_id).status, "completed")
        with self.assertRaisesRegex(SchedulerError, "terminal"):
            self.scheduler.manual_takeover(run.run_id)

    def test_resume_rejects_non_standard_values_without_context_mutation(self) -> None:
        self.scheduler.add_executor(self.first.agent_id,lambda _context:ExecutionResult("completed",{}))
        run=self.scheduler.start("tenant","project",(self.first.agent_id,),{"original":True},auto_run=False)
        run=self.scheduler.pause(run.run_id)
        for values in ({"value":float("nan")},{"value":object()}):
            with self.subTest(values=values),self.assertRaisesRegex(SchedulerError,"standard JSON"):
                self.scheduler.resume(run.run_id,values)
        self.assertEqual(dict(self.scheduler.contexts.get("tenant","project",self.first.agent_id).values),{"original":True})

    def test_manual_takeover_and_retry_limit(self) -> None:
        self.scheduler.add_executor(self.first.agent_id, lambda context: ExecutionResult("failed", {}))
        run = self.scheduler.start("tenant", "project", (self.first.agent_id,), {}, max_retries=0)
        self.assertEqual(self.scheduler.manual_takeover(run.run_id).status, "waiting_human")
        self.scheduler.runs[run.run_id] = run
        with self.assertRaisesRegex(SchedulerError, "maximum retries"):
            self.scheduler.retry(run.run_id)

    def test_active_agent_executor_cannot_be_replaced_or_double_run(self) -> None:
        entered=threading.Event();release=threading.Event()
        def slow(context):entered.set();release.wait(2);return ExecutionResult("completed",{})
        self.scheduler.add_executor(self.first.agent_id,slow)
        first=self.scheduler.start("tenant","project-a",(self.first.agent_id,),{},auto_run=False)
        second=self.scheduler.start("tenant","project-b",(self.first.agent_id,),{},auto_run=False)
        thread=threading.Thread(target=lambda:self.scheduler.run(first.run_id));thread.start();self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(SchedulerError,"active"):self.scheduler.add_executor(self.first.agent_id,lambda _:ExecutionResult("completed",{}))
        with self.assertRaisesRegex(SchedulerError,"already active"):self.scheduler.run(second.run_id)
        release.set();thread.join()

    def test_pipeline_rejects_duplicate_agents(self) -> None:
        with self.assertRaisesRegex(SchedulerError,"unique"):
            self.scheduler.start("tenant","project",(self.first.agent_id,self.first.agent_id),{},auto_run=False)

    def test_pipeline_and_graph_orchestrator_require_valid_identity_contracts(self) -> None:
        for scope in (("", "project"), ("tenant", "")):
            with self.assertRaisesRegex(SchedulerError, "tenant_id and project_id"):
                self.scheduler.start(*scope, (self.first.agent_id,), {}, auto_run=False)
        for operation in (lambda:self.scheduler.add_executor(1,lambda _:None),lambda:self.scheduler.start("tenant","project",(self.first.agent_id,),{},mode=1,auto_run=False)):
            with self.subTest(operation=operation),self.assertRaises(SchedulerError):operation()
        with self.assertRaisesRegex(SchedulerError, "contract"):
            self.scheduler.use_graph_orchestrator(object())

    def test_anonymous_run_and_invalid_remediation_controls_are_rejected(self) -> None:
        with self.assertRaisesRegex(SchedulerError, "run_id"):self.scheduler.run("")
        with self.assertRaisesRegex(SchedulerError, "instruction_id"):self.scheduler.remediation("")
        invalid=RemediationInstruction("", "session", "report", self.first.agent_id, "task", ("issue",), 1, "pending", "now")
        with self.assertRaisesRegex(SchedulerError, "contract"):self.scheduler.schedule_remediation(invalid)
        invalid=RemediationInstruction("instruction", "session", "report", self.first.agent_id, "task", (1,), 1, "pending", "now")
        with self.assertRaisesRegex(SchedulerError,"contract"):self.scheduler.schedule_remediation(invalid)

    def test_executor_result_runtime_contract_is_enforced(self) -> None:
        self.scheduler.add_executor(self.first.agent_id,lambda _context:object())
        run=self.scheduler.start("tenant","project",(self.first.agent_id,),{},auto_run=False)
        with self.assertRaisesRegex(SchedulerError,"result"):self.scheduler.run(run.run_id)


if __name__ == "__main__": unittest.main()
