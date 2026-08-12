"""Provider configuration and live connection health management."""
from __future__ import annotations
from dataclasses import dataclass,replace
from datetime import datetime,timezone
from types import MappingProxyType
from threading import RLock
from typing import Any,Mapping,Protocol
from urllib.parse import urlparse
class ProviderServiceError(ValueError):pass
class ProviderHealthChecker(Protocol):
    def check(self,provider:"ProviderConfiguration")->tuple[int|None,str|None]:...
@dataclass(frozen=True,slots=True)
class ProviderConfiguration:
    provider_id:str;display_name:str;kind:str;endpoint:str;secret_reference:str;capabilities:tuple[str,...];enabled:bool;timeout_seconds:int;settings:Mapping[str,Any];created_at:str;updated_at:str
@dataclass(frozen=True,slots=True)
class ProviderHealth:
    provider_id:str;status:str;checked_at:str;latency_ms:int|None;error_code:str|None;consecutive_failures:int
class ProviderService:
    def __init__(self,checker:ProviderHealthChecker|None=None):
        if checker is not None and not callable(getattr(checker,"check",None)):raise ProviderServiceError("provider health checker contract is invalid")
        self.checker=checker;self.configurations={};self.health={};self._lock=RLock()
    def register(self,*,provider_id:str,display_name:str,kind:str,endpoint:str,secret_reference:str,capabilities:tuple[str,...],enabled:bool=True,timeout_seconds:int=60,settings:Mapping[str,Any]|None=None)->ProviderConfiguration:
        if isinstance(capabilities,(str,bytes)) or not isinstance(capabilities,(tuple,list,set,frozenset)) or any(not isinstance(value,str) for value in capabilities):raise ProviderServiceError("provider configuration is invalid")
        provider_id,display_name,kind,endpoint,secret_reference=(str(value).strip() for value in (provider_id,display_name,kind,endpoint,secret_reference));capabilities=tuple(value.strip() for value in capabilities)
        parsed=urlparse(endpoint);local_http=parsed.scheme=="http" and parsed.hostname in {"127.0.0.1","localhost","::1"}
        valid_https=parsed.scheme=="https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.fragment
        if (not provider_id or not display_name or kind not in {"model","text","image","video","audio"} or not (valid_https or local_http)
            or not secret_reference.startswith(("env://","vault://","secret://")) or not capabilities or any(not value for value in capabilities)
            or len(set(capabilities))!=len(capabilities) or isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,int) or timeout_seconds<1
            or not isinstance(enabled,bool) or settings is not None and not isinstance(settings,Mapping)):raise ProviderServiceError("provider configuration is invalid")
        forbidden=("secret","token","password","api_key","authorization","credential")
        def contains_secret(value:Any)->bool:
            if isinstance(value,Mapping):return any(any(word in str(key).lower() for word in forbidden) or contains_secret(item) for key,item in value.items())
            if isinstance(value,(list,tuple)):return any(contains_secret(item) for item in value)
            return False
        if contains_secret(settings or {}):raise ProviderServiceError("provider settings cannot contain secrets")
        with self._lock:
            if provider_id in self.configurations:raise ProviderServiceError("provider already exists")
            now=self._now();item=ProviderConfiguration(provider_id,display_name,kind,endpoint,secret_reference,capabilities,enabled,timeout_seconds,MappingProxyType(dict(settings or {})),now,now);self.configurations[provider_id]=item;self.health[provider_id]=ProviderHealth(provider_id,"unknown",now,None,None,0);return item
    def get(self,provider_id:str)->ProviderConfiguration:
        provider_id=provider_id.strip()
        if not provider_id:raise ProviderServiceError("provider id is required")
        with self._lock:
            try:return self.configurations[provider_id]
            except KeyError as error:raise ProviderServiceError("provider not found") from error
    def list(self)->tuple[ProviderConfiguration,...]:
        with self._lock:return tuple(sorted(self.configurations.values(),key=lambda x:x.provider_id))
    def test_connection(self,provider_id:str)->ProviderHealth:
        with self._lock:provider=self.get(provider_id);previous=self.health[provider_id]
        if not provider.enabled:item=ProviderHealth(provider_id,"disabled",self._now(),None,None,previous.consecutive_failures)
        elif self.checker is None:raise ProviderServiceError("real provider health checker is not configured")
        else:
            latency,error=self.checker.check(provider);failures=previous.consecutive_failures+1 if error else 0;item=ProviderHealth(provider_id,"healthy" if not error else "degraded" if failures<3 else "unhealthy",self._now(),latency,error,failures)
        with self._lock:
            current=self.health[provider_id]
            if current is not previous:raise ProviderServiceError("provider health changed concurrently; retry")
            self.health[provider_id]=item;return item
    @staticmethod
    def _now():return datetime.now(timezone.utc).isoformat()
