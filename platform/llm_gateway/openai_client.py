"""OpenAI-compatible production client with timeout, cancellation and schema checks."""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
from threading import Event
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from .model_registry import ModelDefinition

class OpenAIClientError(RuntimeError): pass
class OpenAIClientTimeout(OpenAIClientError): pass
class OpenAIClientCancelled(OpenAIClientError): pass
class OpenAIResponseError(OpenAIClientError): pass

@dataclass(frozen=True, slots=True)
class OpenAITransportResponse:
    status: int
    body: bytes

class OpenAITransport(Protocol):
    def post(self, url:str, headers:Mapping[str,str], body:bytes, timeout_seconds:float, cancellation:Event|None) -> OpenAITransportResponse: ...

class UrllibOpenAITransport:
    def post(self,url:str,headers:Mapping[str,str],body:bytes,timeout_seconds:float,cancellation:Event|None)->OpenAITransportResponse:
        if cancellation and cancellation.is_set(): raise OpenAIClientCancelled("model request cancelled")
        try:
            with urlopen(Request(url,data=body,headers=dict(headers),method="POST"),timeout=timeout_seconds) as response:
                payload=response.read(); status=response.status
        except HTTPError as error:
            raise OpenAIClientError(f"model provider HTTP {error.code}") from error
        except TimeoutError as error: raise OpenAIClientTimeout("model provider timed out") from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError): raise OpenAIClientTimeout("model provider timed out") from error
            raise OpenAIClientError("model provider unavailable") from error
        if cancellation and cancellation.is_set(): raise OpenAIClientCancelled("model request cancelled")
        return OpenAITransportResponse(status,payload)

class OpenAICompatibleClient:
    def __init__(self,*,endpoint:str,api_key:str,timeout_seconds:float=60,transport:OpenAITransport|None=None) -> None:
        if not isinstance(endpoint,str) or not isinstance(api_key,str):raise OpenAIClientError("model endpoint and secret must be strings")
        endpoint=endpoint.rstrip("/"); api_key=api_key.strip()
        parsed=urlparse(endpoint)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment: raise OpenAIClientError("model endpoint must use a valid HTTPS origin")
        if not api_key: raise OpenAIClientError("model provider secret is required")
        if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or timeout_seconds<=0 or not math.isfinite(timeout_seconds): raise OpenAIClientError("timeout_seconds must be positive")
        selected_transport=transport or UrllibOpenAITransport()
        if not callable(getattr(selected_transport,"post",None)):raise OpenAIClientError("model transport contract is invalid")
        self._endpoint=endpoint; self._api_key=api_key; self._timeout=timeout_seconds; self._transport=selected_transport

    def complete(self,model:ModelDefinition,messages:Sequence[Any],response_schema:Mapping[str,Any],*,cancellation:Event|None=None)->Mapping[str,Any]:
        if (not isinstance(model,ModelDefinition) or isinstance(messages,(str,bytes)) or not isinstance(messages,Sequence) or not isinstance(response_schema,Mapping)
                or any(not isinstance(getattr(item,"role",None),str) or not getattr(item,"role").strip() or not isinstance(getattr(item,"content",None),str) for item in messages)):raise OpenAIClientError("model request contract is invalid")
        if cancellation is not None and not callable(getattr(cancellation,"is_set",None)):raise OpenAIClientError("cancellation contract is invalid")
        if cancellation and cancellation.is_set(): raise OpenAIClientCancelled("model request cancelled")
        request={"model":model.model_id,"messages":[{"role":item.role,"content":item.content} for item in messages],"response_format":{"type":"json_schema","json_schema":{"name":"agent_response","strict":True,"schema":dict(response_schema)}}}
        try:request_body=json.dumps(request,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
        except (TypeError,ValueError) as error:raise OpenAIClientError("model request must be standard JSON") from error
        response=self._transport.post(f"{self._endpoint}/chat/completions",{"Authorization":f"Bearer {self._api_key}","Content-Type":"application/json"},request_body,self._timeout,cancellation)
        if not isinstance(response,OpenAITransportResponse) or isinstance(response.status,bool) or not isinstance(response.status,int) or not isinstance(response.body,bytes):raise OpenAIResponseError("model transport response is invalid")
        if response.status<200 or response.status>=300: raise OpenAIClientError(f"model provider HTTP {response.status}")
        try:
            envelope=json.loads(response.body); content=envelope["choices"][0]["message"]["content"]
            result=json.loads(content) if isinstance(content,str) else content
        except (ValueError,KeyError,IndexError,TypeError,json.JSONDecodeError) as error: raise OpenAIResponseError("model provider response is invalid") from error
        if not isinstance(result,Mapping): raise OpenAIResponseError("structured model response must be an object")
        try:json.dumps(dict(result),allow_nan=False)
        except (TypeError,ValueError) as error:raise OpenAIResponseError("structured model response must be standard JSON") from error
        self._validate(result,response_schema)
        return result

    @classmethod
    def _validate(cls,value:Any,schema:Mapping[str,Any],path:str="$")->None:
        expected=schema.get("type")
        allowed=expected if isinstance(expected,list) else [expected] if expected else []
        matches={"object":isinstance(value,Mapping),"array":isinstance(value,list),"string":isinstance(value,str),"number":isinstance(value,(int,float)) and not isinstance(value,bool),"integer":isinstance(value,int) and not isinstance(value,bool),"boolean":isinstance(value,bool),"null":value is None}
        if allowed and not any(matches.get(item,False) for item in allowed): raise OpenAIResponseError(f"structured response type mismatch at {path}")
        if isinstance(value,Mapping):
            missing=set(schema.get("required",[]))-value.keys()
            if missing: raise OpenAIResponseError(f"structured response missing required fields at {path}")
            properties=schema.get("properties",{})
            for key,child in value.items():
                if key in properties: cls._validate(child,properties[key],f"{path}.{key}")
        if "enum" in schema and value not in schema["enum"]: raise OpenAIResponseError(f"structured response enum mismatch at {path}")
