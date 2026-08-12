"""Bounded rate limiting, retries, circuit breaking and provider fallback."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import time
import math
from threading import RLock
from typing import Any,Callable,Mapping

class ProviderCallError(RuntimeError):
    def __init__(self,code:str,message:str,*,retryable:bool,provider_id:str):super().__init__(message);self.code=code;self.retryable=retryable;self.provider_id=provider_id
def normalize_provider_error(error:Exception,provider_id:str)->ProviderCallError:
    if isinstance(error,ProviderCallError):return error
    if "timeout" in type(error).__name__.lower():return ProviderCallError("PROVIDER_TIMEOUT","provider timed out",retryable=True,provider_id=provider_id)
    if isinstance(error,(ConnectionError,OSError)):return ProviderCallError("PROVIDER_UNAVAILABLE","provider unavailable",retryable=True,provider_id=provider_id)
    if isinstance(error,ValueError):return ProviderCallError("PROVIDER_INVALID_RESPONSE","provider response invalid",retryable=False,provider_id=provider_id)
    return ProviderCallError("PROVIDER_ERROR","provider request failed",retryable=False,provider_id=provider_id)
class SlidingWindowRateLimiter:
    def __init__(self,limit:int,clock:Callable[[],float]=time.monotonic):
        if isinstance(limit,bool) or not isinstance(limit,int) or limit<1 or not callable(clock):raise ValueError("rate limit and clock must be valid")
        self.limit=limit;self.clock=clock;self.calls:deque[float]=deque();self._lock=RLock()
    def acquire(self,provider_id:str)->None:
        if not isinstance(provider_id,str) or not provider_id.strip():raise ValueError("provider id is required")
        with self._lock:
            now=self.clock()
            if isinstance(now,bool) or not isinstance(now,(int,float)) or not math.isfinite(now):raise ValueError("rate limiter clock must be finite")
            while self.calls and now-self.calls[0]>=60:self.calls.popleft()
            if len(self.calls)>=self.limit:raise ProviderCallError("PROVIDER_RATE_LIMITED","provider rate limit exceeded",retryable=True,provider_id=provider_id)
            self.calls.append(now)
@dataclass(slots=True)
class CircuitState: failures:int=0;opened_at:float|None=None
class CircuitBreaker:
    def __init__(self,threshold:int=3,recovery_seconds:float=30,clock:Callable[[],float]=time.monotonic):
        if (isinstance(threshold,bool) or not isinstance(threshold,int) or threshold<1
                or isinstance(recovery_seconds,bool) or not isinstance(recovery_seconds,(int,float)) or recovery_seconds<=0
                or not math.isfinite(recovery_seconds)
                or not callable(clock)):raise ValueError("circuit threshold and recovery must be positive and clock callable")
        self.threshold=threshold;self.recovery_seconds=recovery_seconds;self.clock=clock;self.states:dict[str,CircuitState]={};self._lock=RLock()
    def before_call(self,p:str)->None:
        p=self._provider(p)
        with self._lock:
            s=self.states.setdefault(p,CircuitState())
            now=self._now()
            if s.opened_at is not None and now-s.opened_at<self.recovery_seconds:raise ProviderCallError("PROVIDER_CIRCUIT_OPEN","provider circuit is open",retryable=True,provider_id=p)
    def success(self,p:str)->None:
        p=self._provider(p)
        with self._lock:self.states[p]=CircuitState()
    def failure(self,p:str)->None:
        p=self._provider(p)
        with self._lock:
            s=self.states.setdefault(p,CircuitState());s.failures+=1
            if s.failures>=self.threshold:s.opened_at=self._now()
    def status(self,p:str)->str:
        p=self._provider(p)
        with self._lock:
            s=self.states.get(p,CircuitState());return "open" if s.opened_at is not None and self._now()-s.opened_at<self.recovery_seconds else "closed"
    @staticmethod
    def _provider(value:str)->str:
        if not isinstance(value,str) or not value.strip():raise ValueError("provider id is required")
        return value.strip()
    def _now(self)->float:
        value=self.clock()
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError("circuit clock must be finite")
        return float(value)
class ResilientProviderInvoker:
    def __init__(self,invoke:Callable[[str,str,Mapping[str,Any]],Any],*,max_retries:int=2,rate_limit:int=60,circuit_threshold:int=3,recovery_seconds:float=30,sleeper:Callable[[float],None]=time.sleep,clock:Callable[[],float]=time.monotonic):
        if not callable(invoke) or not callable(sleeper) or not callable(clock):raise ValueError("provider invoker callables are required")
        if isinstance(max_retries,bool) or not isinstance(max_retries,int) or not 0<=max_retries<=10:raise ValueError("invalid retry limit")
        if isinstance(rate_limit,bool) or not isinstance(rate_limit,int) or rate_limit<1:raise ValueError("invalid rate limit")
        self.invoke=invoke;self.max_retries=max_retries;self.rate_limit=rate_limit;self.sleeper=sleeper;self.clock=clock;self.breaker=CircuitBreaker(circuit_threshold,recovery_seconds,clock);self.limiters:dict[str,SlidingWindowRateLimiter]={};self._lock=RLock()
    def call(self,provider_id:str,capability:str,inputs:Mapping[str,Any],*,fallback_provider_ids:tuple[str,...]=())->Any:
        targets=(provider_id,*fallback_provider_ids)
        if (not isinstance(provider_id,str) or not isinstance(capability,str) or not isinstance(fallback_provider_ids,tuple)
                or not provider_id.strip() or not capability.strip() or any(not isinstance(target,str) or not target.strip() for target in targets)):raise ValueError("provider and capability are required")
        if len(set(targets))!=len(targets):raise ValueError("provider fallback chain must be unique")
        if not isinstance(inputs,Mapping):raise ValueError("provider inputs must be a mapping")
        last=None
        for target in targets:
            with self._lock:limiter=self.limiters.setdefault(target,SlidingWindowRateLimiter(self.rate_limit,self.clock))
            for attempt in range(self.max_retries+1):
                try:self.breaker.before_call(target);limiter.acquire(target);result=self.invoke(target,capability,inputs);self.breaker.success(target);return result
                except Exception as raw:
                    last=normalize_provider_error(raw,target);self.breaker.failure(target)
                    if not last.retryable or attempt>=self.max_retries:break
                    self.sleeper(min(2**attempt,4))
        assert last is not None;raise last
