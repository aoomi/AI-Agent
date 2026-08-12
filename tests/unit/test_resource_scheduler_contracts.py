from __future__ import annotations

import unittest
import math
import threading

from ai_agent_core import ResourceScheduler, ResourceSchedulerError


class ResourceSchedulerContractTest(unittest.TestCase):
    def test_constructor_rejects_pseudo_integer_pool_limits(self) -> None:
        for kwargs in ({"pool_capacities":{"global":True}},{"pool_queue_limits":{"global":1.5}},
                       {"pool_capacities":{"unused":1}}, {"resource_pools":{"unknown":"global"}},
                       {"serialized_pools":{"unused"}}, {"resource_pools":[]},
                       {"serialized_pools":["global"]}, {"execution_lock":object()}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                ResourceScheduler(**kwargs)  # type: ignore[arg-type]

    def test_claim_rejects_invalid_runtime_numeric_controls(self) -> None:
        scheduler = ResourceScheduler()
        for memory in (True, 1.5):
            with self.subTest(memory=memory), self.assertRaisesRegex(ResourceSchedulerError, "invalid resource request"):
                with scheduler.claim("video", "job-1", estimated_memory=memory):  # type: ignore[arg-type]
                    pass
        for timeout in (0, -1, True, math.nan, math.inf):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(ResourceSchedulerError, "timeout must be positive"):
                with scheduler.claim("video", "job-1", timeout=timeout):  # type: ignore[arg-type]
                    pass
        self.assertEqual(scheduler.snapshot()["queued"], [])

    def test_resource_identity_controls_require_strings(self) -> None:
        scheduler=ResourceScheduler()
        for operation in (
            lambda:scheduler.claim(1,"job").__enter__(), lambda:scheduler.claim("video",1).__enter__(),
            lambda:scheduler.claim("video","job",tenant_id=1).__enter__(), lambda:scheduler.cancel_job(1),
            lambda:scheduler.cancel_job("job",project_id=1),
        ):
            with self.subTest(operation=operation),self.assertRaises(ResourceSchedulerError):operation()
        self.assertEqual(scheduler.snapshot()["queued"],[])

    def test_same_scoped_job_is_single_flight(self) -> None:
        scheduler=ResourceScheduler();entered=threading.Event();release=threading.Event()
        def hold():
            with scheduler.claim("video","job",tenant_id="t",user_id="u",project_id="p"):
                entered.set();release.wait(2)
        thread=threading.Thread(target=hold);thread.start();self.assertTrue(entered.wait(1))
        try:
            with self.assertRaisesRegex(ResourceSchedulerError,"already queued or active"):
                with scheduler.claim("video","job",tenant_id="t",user_id="u",project_id="p"):pass
        finally:
            release.set();thread.join()


if __name__ == "__main__":
    unittest.main()
