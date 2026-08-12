from __future__ import annotations

import unittest
import math

from ai_agent_core import ResourceScheduler, ResourceSchedulerError


class ResourceSchedulerContractTest(unittest.TestCase):
    def test_constructor_rejects_pseudo_integer_pool_limits(self) -> None:
        for kwargs in ({"pool_capacities":{"global":True}},{"pool_queue_limits":{"global":1.5}},
                       {"pool_capacities":{"unused":1}}, {"resource_pools":{"unknown":"global"}},
                       {"serialized_pools":{"unused"}}):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,"pool"):
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


if __name__ == "__main__":
    unittest.main()
