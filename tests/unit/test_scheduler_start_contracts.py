from __future__ import annotations

import unittest

from ai_agent_core import AgentContextStore, AgentScheduler, SchedulerError
from ai_agent_discovery import AgentRegistry


class SchedulerStartContractTest(unittest.TestCase):
    def test_start_rejects_runtime_contract_errors_before_context_creation(self) -> None:
        contexts=AgentContextStore(); scheduler=AgentScheduler(AgentRegistry(),contexts)
        for operation in (
            lambda:scheduler.start("tenant","project",(" ",),{},auto_run=False),
            lambda:scheduler.start("tenant","project",("agent",),[],auto_run=False),
            lambda:scheduler.start("tenant","project",("agent",),{},max_retries=True,auto_run=False),
            lambda:scheduler.start("tenant","project",("agent",),{},auto_run=1),
        ):
            with self.subTest(operation=operation),self.assertRaises(SchedulerError):operation()
        self.assertEqual(scheduler.runs,{})

    def test_start_rejects_non_standard_values_without_partial_contexts(self) -> None:
        contexts=AgentContextStore();scheduler=AgentScheduler(AgentRegistry(),contexts)
        for values in ({"value":float("nan")},{"value":object()}):
            with self.subTest(values=values),self.assertRaisesRegex(SchedulerError,"standard JSON"):
                scheduler.start("tenant","project",("agent",),values,auto_run=False)
            with self.assertRaisesRegex(Exception,"does not exist"):
                contexts.get("tenant","project","agent")


if __name__=="__main__":unittest.main()
