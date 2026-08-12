from __future__ import annotations

import unittest
import math

from ai_agent_circuit_breaker import CircuitBreaker, ResilientProviderInvoker, SlidingWindowRateLimiter


class ProviderResilienceContractTest(unittest.TestCase):
    def test_constructors_reject_pseudo_numeric_and_bad_callables(self) -> None:
        for build in (
            lambda: SlidingWindowRateLimiter(True), lambda: SlidingWindowRateLimiter(1, clock=None),
            lambda: CircuitBreaker(True), lambda: CircuitBreaker(recovery_seconds=True),
            lambda: CircuitBreaker(recovery_seconds=math.inf),
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
        for inputs in ({"value":math.nan},{"value":object()}):
            with self.subTest(inputs=inputs),self.assertRaisesRegex(ValueError,"standard JSON"):invoker.call("provider","video",inputs)
        self.assertEqual(calls,[])

    def test_provider_cannot_mutate_nested_caller_inputs(self) -> None:
        def invoke(_provider,_capability,inputs):inputs["routing"]["regions"][0]="provider";return {"ok":True}
        inputs={"routing":{"regions":["local"]}}
        ResilientProviderInvoker(invoke).call("provider","video",inputs)
        self.assertEqual(inputs["routing"]["regions"][0],"local")

    def test_runtime_identities_and_non_finite_clocks_are_rejected(self) -> None:
        invoker=ResilientProviderInvoker(lambda *_: None)
        for call in (lambda:invoker.call(1,"video",{}),lambda:invoker.call("p","video",{},fallback_provider_ids=["q"]),lambda:CircuitBreaker(clock=lambda:math.nan).before_call("p"),lambda:SlidingWindowRateLimiter(1,clock=lambda:math.inf).acquire("p"),lambda:CircuitBreaker().status(1)):
            with self.subTest(call=call),self.assertRaises(ValueError):call()


if __name__ == "__main__":
    unittest.main()
