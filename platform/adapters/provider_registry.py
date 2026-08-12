"""Authorized real-provider adapter registration for text and media capabilities."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from threading import RLock
from typing import Any, Mapping, Protocol
import json

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
        if any(not isinstance(value,str) for value in (self.provider_id,self.kind,self.secret_reference)):
            raise ProviderAdapterError("provider definition fields must be strings")
        if not isinstance(self.capabilities,frozenset):raise ProviderAdapterError("provider capabilities must be a frozenset")
        if self.kind not in {"model","text","image","video","audio"}: raise ProviderAdapterError("provider kind is invalid")
        if not self.provider_id.strip() or not self.capabilities or any(not isinstance(value,str) or not value.strip() for value in self.capabilities): raise ProviderAdapterError("provider id and capabilities are required")
        if not self.secret_reference.startswith(("env://","vault://","secret://")): raise ProviderAdapterError("provider requires an external secret reference")
        if isinstance(self.timeout_seconds,bool) or not isinstance(self.timeout_seconds,int) or self.timeout_seconds<1: raise ProviderAdapterError("provider timeout must be positive")
        if not isinstance(self.enabled,bool):raise ProviderAdapterError("provider enabled must be boolean")
        if self.settings is not None and not isinstance(self.settings,Mapping):raise ProviderAdapterError("provider settings must be a mapping")
        forbidden=("secret","token","password","api_key","authorization","credential")
        def contains_secret(value:Any)->bool:
            if isinstance(value,Mapping):return any(any(word in str(key).lower() for word in forbidden) or contains_secret(item) for key,item in value.items())
            if isinstance(value,(list,tuple)):return any(contains_secret(item) for item in value)
            return False
        if contains_secret(self.settings or {}):raise ProviderAdapterError("provider settings cannot contain secrets")
        try:json.dumps(dict(self.settings or {}),allow_nan=False)
        except (TypeError,ValueError) as error:raise ProviderAdapterError("provider settings must be standard JSON") from error
        object.__setattr__(self,"settings",MappingProxyType(dict(self.settings or {})))

@dataclass(frozen=True, slots=True)
class ProviderInvocation:
    provider_id:str
    kind:str
    capability:str
    output:Any

class ProviderAdapterRegistry:
    def __init__(self,secret_resolver:SecretResolver)->None:
        if not callable(getattr(secret_resolver,"resolve",None)):raise ProviderAdapterError("secret resolver contract is invalid")
        self._resolver=secret_resolver;self._providers:dict[str,tuple[ProviderAdapterDefinition,ProviderExecutor]]={};self._lock=RLock();self._inflight:dict[str,int]={}
    def register(self,definition:ProviderAdapterDefinition,executor:ProviderExecutor,*,replace:bool=False)->tuple[ProviderAdapterDefinition,bool]:
        if not isinstance(definition,ProviderAdapterDefinition):raise ProviderAdapterError("provider definition contract is invalid")
        if not callable(getattr(executor,"execute",None)):raise ProviderAdapterError("provider executor contract is invalid")
        if not isinstance(replace,bool):raise ProviderAdapterError("provider replace control must be boolean")
        with self._lock:
            existing=self._providers.get(definition.provider_id)
            if existing:
                if existing==(definition,executor):return definition,True
                if not replace:raise ProviderAdapterError(f"conflicting provider id: {definition.provider_id}")
                if self._inflight.get(definition.provider_id,0):raise ProviderAdapterError(f"provider has in-flight invocations: {definition.provider_id}")
                self._providers[definition.provider_id]=(definition,executor);return definition,False
            self._providers[definition.provider_id]=(definition,executor);return definition,False
    def unregister(self,provider_id:str)->bool:
        if not isinstance(provider_id,str) or not provider_id.strip():raise ProviderAdapterError("provider id is required")
        provider_id=provider_id.strip()
        with self._lock:
            if self._inflight.get(provider_id,0):raise ProviderAdapterError(f"provider has in-flight invocations: {provider_id}")
            return self._providers.pop(provider_id,None) is not None
    def get(self,provider_id:str)->ProviderAdapterDefinition:
        if not isinstance(provider_id,str):raise ProviderAdapterError("provider id is required")
        provider_id=provider_id.strip()
        if not provider_id:raise ProviderAdapterError("provider id is required")
        with self._lock:
            try:return self._providers[provider_id][0]
            except KeyError as error:raise ProviderAdapterError(f"unknown provider: {provider_id}") from error
    def list(self,*,kind:str|None=None)->tuple[ProviderAdapterDefinition,...]:
        if kind is not None and (not isinstance(kind,str) or kind not in {"model","text","image","video","audio"}):raise ProviderAdapterError("provider kind is invalid")
        with self._lock:return tuple(sorted((d for d,_ in self._providers.values() if kind is None or d.kind==kind),key=lambda d:d.provider_id))
    def invoke(self,provider_id:str,capability:str,inputs:Mapping[str,Any])->ProviderInvocation:
        if not isinstance(provider_id,str) or not isinstance(capability,str):raise ProviderAdapterError("provider, capability and mapping inputs are required")
        provider_id,capability=provider_id.strip(),capability.strip()
        if not provider_id or not capability or not isinstance(inputs,Mapping):raise ProviderAdapterError("provider, capability and mapping inputs are required")
        try:json.dumps(dict(inputs),allow_nan=False)
        except (TypeError,ValueError) as error:raise ProviderAdapterError("provider inputs must be standard JSON") from error
        with self._lock:
            try:definition,executor=self._providers[provider_id]
            except KeyError as error:raise ProviderAdapterError(f"unknown provider: {provider_id}") from error
            if not definition.enabled:raise ProviderAdapterError("provider is disabled")
            if capability not in definition.capabilities:raise ProviderAdapterError("provider capability is not authorized")
            self._inflight[provider_id]=self._inflight.get(provider_id,0)+1
        try:
            secret=self._resolver.resolve(definition.secret_reference)
            if not isinstance(secret,str) or not secret:raise ProviderAdapterError("provider secret could not be resolved")
            output=executor.execute(capability,MappingProxyType(dict(inputs)),secret=secret,timeout_seconds=definition.timeout_seconds)
            if output is None:raise ProviderAdapterError("provider returned no output")
            return ProviderInvocation(provider_id,definition.kind,capability,output)
        finally:
            with self._lock:
                remaining=self._inflight.get(provider_id,1)-1
                if remaining:self._inflight[provider_id]=remaining
                else:self._inflight.pop(provider_id,None)
