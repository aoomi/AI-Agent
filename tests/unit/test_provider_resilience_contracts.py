from __future__ import annotations

import unittest

from ai_agent_circuit_breaker import CircuitBreaker, ResilientProviderInvoker, SlidingWindowRateLimiter


class ProviderResilienceContractTest(unittest.TestCase):
    def test_constructors_reject_pseudo_numeric_and_bad_callables(self) -> None:
        for build in (
            lambda: SlidingWindowRateLimiter(True), lambda: SlidingWindowRateLimiter(1, clock=None),
            lambda: CircuitBreaker(True), lambda: CircuitBreaker(recovery_seconds=True),
            lambda: ResilientProviderInvoker(None), lambda: ResilientProviderInvoker(lambda *_: None, max_retries=True),
            lambda: ResilientProviderInvoker(lambda *_: None, rate_limit=True),
        ):
            with self.subTest(build=build), self.assertRaises(ValueError):
                build()

    def test_call_rejects_non_mapping_inputs_before_provider(self) -> None:
        calls=[]
        invoker=ResilientProviderInvoker(lambda *args: calls.append(args))
        with self.assertRaisesRegex(ValueError,"inputs must be a mapping"):
            invoker.call("provider","video",[])  # type: ignore[arg-type]
        self.assertEqual(calls,[])


if __name__ == "__main__":
    unittest.main()
