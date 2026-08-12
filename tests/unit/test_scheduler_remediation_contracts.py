from __future__ import annotations

import unittest

from ai_agent_core import AgentContextStore, AgentScheduler, RemediationInstruction, SchedulerError
from ai_agent_discovery import AgentRegistry


class SchedulerRemediationContractTest(unittest.TestCase):
    def test_remediation_rejects_empty_issues_and_pseudo_round(self) -> None:
        scheduler=AgentScheduler(AgentRegistry(),AgentContextStore())
        for instruction in (
            RemediationInstruction("id","session","report","developer","task",(" ",),1,"pending","now"),
            RemediationInstruction("id","session","report","developer","task",("issue",),True,"pending","now"),
        ):
            with self.subTest(instruction=instruction),self.assertRaisesRegex(SchedulerError,"contract is invalid"):
                scheduler.schedule_remediation(instruction)
        self.assertEqual(scheduler.remediations,{})


if __name__=="__main__":unittest.main()
