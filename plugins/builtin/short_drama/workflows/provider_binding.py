"""Bind every short-drama generation node to authorized provider adapters."""
from __future__ import annotations
import base64
from typing import Any,Mapping,Sequence
from ai_agent_adapters import ProviderAdapterRegistry
from .delivery_pipeline import DeliveryOutput,ReviewDecision
from .media_pipeline import ProviderOutput

class ShortDramaProviderBindingError(ValueError):pass
class ShortDramaProviderBindings:
    REQUIRED=("short_drama.outline","short_drama.script","short_drama.storyboard","short_drama.assets","short_drama.image","short_drama.video","short_drama.audio","short_drama.subtitle","short_drama.composition","short_drama.review")
    def __init__(self,registry:ProviderAdapterRegistry,routes:Mapping[str,str]):
        if not isinstance(registry,ProviderAdapterRegistry) or not isinstance(routes,Mapping) or any(not isinstance(key,str) or not isinstance(value,str) or not value.strip() for key,value in routes.items()):raise ShortDramaProviderBindingError("provider routes are invalid")
        missing=set(self.REQUIRED)-routes.keys()
        if missing:raise ShortDramaProviderBindingError(f"missing provider routes: {sorted(missing)}")
        self.registry=registry;self.routes=dict(routes)
    @classmethod
    def _provider_inputs(cls,value:Any)->Any:
        if isinstance(value,bytes):return {"encoding":"base64","data":base64.b64encode(value).decode("ascii")}
        if isinstance(value,Mapping):return {str(key):cls._provider_inputs(item) for key,item in value.items()}
        if isinstance(value,(list,tuple)):return [cls._provider_inputs(item) for item in value]
        return value
    def _invoke(self,capability:str,inputs:Mapping[str,Any])->Any:return self.registry.invoke(self.routes[capability],capability,self._provider_inputs(inputs)).output
    def generate(self,capability:str,inputs:Mapping[str,Any]):
        output=self._invoke(capability,inputs)
        if capability in {"short_drama.outline","short_drama.script","short_drama.storyboard"}:
            if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("text provider output must be an object")
            return output
        if not isinstance(output,Sequence) or isinstance(output,(str,bytes)):raise ShortDramaProviderBindingError("media provider output must be an array")
        values=[]
        for item in output:
            if not isinstance(item,Mapping):raise ShortDramaProviderBindingError("media item is invalid")
            try:value=ProviderOutput(item["content"],item["media_type"],item["source_id"],item.get("asset_kind","shot"),item.get("start_ms",0),item.get("end_ms",1))
            except (KeyError,TypeError) as error:raise ShortDramaProviderBindingError("media item is invalid") from error
            if not isinstance(value.content,bytes) or not isinstance(value.media_type,str) or not isinstance(value.source_id,str) or not isinstance(value.asset_kind,str) or any(isinstance(number,bool) or not isinstance(number,int) for number in (value.start_ms,value.end_ms)):
                raise ShortDramaProviderBindingError("media item is invalid")
            values.append(value)
        return tuple(values)
    def compose(self,inputs:Mapping[str,Sequence[bytes]])->DeliveryOutput:
        output=self._invoke("short_drama.composition",inputs)
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("composition output is invalid")
        try:return DeliveryOutput(output["content"],output["media_type"])
        except (KeyError,TypeError) as error:raise ShortDramaProviderBindingError("composition output is invalid") from error
    def review(self,content:bytes,media_type:str)->ReviewDecision:
        output=self._invoke("short_drama.review",{"content":content,"media_type":media_type})
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("review output is invalid")
        approved,issues=output.get("approved"),output.get("issues")
        if not isinstance(approved,bool) or not isinstance(issues,(list,tuple)) or any(not isinstance(issue,str) or not issue.strip() for issue in issues):raise ShortDramaProviderBindingError("review output is invalid")
        return ReviewDecision(approved,tuple(issues))
    def repair(self,content:bytes,media_type:str,issues:tuple[str,...])->DeliveryOutput:
        output=self._invoke("short_drama.composition",{"content":content,"media_type":media_type,"issues":issues,"operation":"repair"})
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("repair output is invalid")
        try:return DeliveryOutput(output["content"],output["media_type"])
        except (KeyError,TypeError) as error:raise ShortDramaProviderBindingError("repair output is invalid") from error
