"""Authorized real-provider adapter registration for text and media capabilities."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from threading import RLock
from typing import Any, Mapping, Protocol

class ProviderAdapterError(ValueError): pass

class ProviderExecutor(Protocol):
    def execute(self, capability:str, inputs:Mapping[str,Any], *, secret:str, timeout_seconds:int) -> Any: ...

class SecretResolver(Protocol):
    def resolve(self, secret_reference:str) -> str: ...

@dataclass(frozen=True, slots=True)
class ProviderAdapterDefinition:
    provider_id:str
    kind:str
    capabilities:frozenset[str]
    secret_reference:str
    timeout_seconds:int
    enabled:bool=True
    settings:Mapping[str,Any]=None  # type: ignore[assignment]
    def __post_init__(self)->None:
        if self.kind not in {"model","text","image","video","audio"}: raise ProviderAdapterError("provider kind is invalid")
        if not self.provider_id.strip() or not self.capabilities: raise ProviderAdapterError("provider id and capabilities are required")
        if not self.secret_reference.startswith(("env://","vault://","secret://")): raise ProviderAdapterError("provider requires an external secret reference")
        if self.timeout_seconds<1: raise ProviderAdapterError("provider timeout must be positive")
        forbidden=("secret","token","password","api_key","authorization","credential")
        def contains_secret(value:Any)->bool:
            if isinstance(value,Mapping):return any(any(word in str(key).lower() for word in forbidden) or contains_secret(item) for key,item in value.items())
            if isinstance(value,(list,tuple)):return any(contains_secret(item) for item in value)
            return False
        if contains_secret(self.settings or {}):raise ProviderAdapterError("provider settings cannot contain secrets")
        object.__setattr__(self,"settings",MappingProxyType(dict(self.settings or {})))

@dataclass(frozen=True, slots=True)
class ProviderInvocation:
    provider_id:str
    kind:str
    capability:str
    output:Any

class ProviderAdapterRegistry:
    def __init__(self,secret_resolver:SecretResolver)->None:self._resolver=secret_resolver;self._providers:dict[str,tuple[ProviderAdapterDefinition,ProviderExecutor]]={};self._lock=RLock();self._inflight:dict[str,int]={}
    def register(self,definition:ProviderAdapterDefinition,executor:ProviderExecutor)->tuple[ProviderAdapterDefinition,bool]:
        with self._lock:
            existing=self._providers.get(definition.provider_id)
            if existing:
                if existing!=(definition,executor):raise ProviderAdapterError(f"conflicting provider id: {definition.provider_id}")
                return definition,True
            self._providers[definition.provider_id]=(definition,executor);return definition,False
    def get(self,provider_id:str)->ProviderAdapterDefinition:
        with self._lock:
            try:return self._providers[provider_id][0]
            except KeyError as error:raise ProviderAdapterError(f"unknown provider: {provider_id}") from error
    def list(self,*,kind:str|None=None)->tuple[ProviderAdapterDefinition,...]:
        with self._lock:return tuple(sorted((d for d,_ in self._providers.values() if kind is None or d.kind==kind),key=lambda d:d.provider_id))
    def invoke(self,provider_id:str,capability:str,inputs:Mapping[str,Any])->ProviderInvocation:
        with self._lock:
            try:definition,executor=self._providers[provider_id]
            except KeyError as error:raise ProviderAdapterError(f"unknown provider: {provider_id}") from error
            if not definition.enabled:raise ProviderAdapterError("provider is disabled")
            if capability not in definition.capabilities:raise ProviderAdapterError("provider capability is not authorized")
            self._inflight[provider_id]=self._inflight.get(provider_id,0)+1
        try:
            secret=self._resolver.resolve(definition.secret_reference)
            if not secret:raise ProviderAdapterError("provider secret could not be resolved")
            output=executor.execute(capability,MappingProxyType(dict(inputs)),secret=secret,timeout_seconds=definition.timeout_seconds)
            if output is None:raise ProviderAdapterError("provider returned no output")
            return ProviderInvocation(provider_id,definition.kind,capability,output)
        finally:
            with self._lock:
                remaining=self._inflight.get(provider_id,1)-1
                if remaining:self._inflight[provider_id]=remaining
                else:self._inflight.pop(provider_id,None)
