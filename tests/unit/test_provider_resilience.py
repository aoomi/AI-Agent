import unittest
from ai_agent_circuit_breaker import ProviderCallError,ResilientProviderInvoker,SlidingWindowRateLimiter
class ProviderResilienceTest(unittest.TestCase):
    def test_retries_then_succeeds(self):
        calls=[]
        def invoke(p,c,i):
            calls.append(p)
            if len(calls)<3:raise TimeoutError()
            return "ok"
        self.assertEqual(ResilientProviderInvoker(invoke,max_retries=2,sleeper=lambda _:None).call("p","c",{}),"ok");self.assertEqual(len(calls),3)
    def test_fallback_and_circuit_open(self):
        calls=[]
        def invoke(p,c,i):calls.append(p);raise ConnectionError()
        service=ResilientProviderInvoker(invoke,max_retries=0,circuit_threshold=1,sleeper=lambda _:None)
        with self.assertRaises(ProviderCallError):service.call("a","c",{},fallback_provider_ids=("b",))
        self.assertEqual(calls,["a","b"]);self.assertEqual(service.breaker.status("a"),"open")
    def test_rate_limit_is_explicit(self):
        limiter=SlidingWindowRateLimiter(1,lambda:0);limiter.acquire("p")
        with self.assertRaisesRegex(ProviderCallError,"rate limit"):limiter.acquire("p")
    def test_invalid_resilience_configuration_and_duplicate_fallback_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"positive"):ResilientProviderInvoker(lambda *_:None,circuit_threshold=0)
        service=ResilientProviderInvoker(lambda *_:"ok")
        with self.assertRaisesRegex(ValueError,"unique"):service.call("p","c",{},fallback_provider_ids=("p",))
if __name__=="__main__":unittest.main()
