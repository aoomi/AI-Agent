"""Bind every short-drama generation node to authorized provider adapters."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from ai_agent_adapters import ProviderAdapterRegistry
from .delivery_pipeline import DeliveryOutput,ReviewDecision
from .media_pipeline import ProviderOutput

class ShortDramaProviderBindingError(ValueError):pass
class ShortDramaProviderBindings:
    REQUIRED=("short_drama.outline","short_drama.script","short_drama.storyboard","short_drama.assets","short_drama.image","short_drama.video","short_drama.audio","short_drama.subtitle","short_drama.composition","short_drama.review")
    def __init__(self,registry:ProviderAdapterRegistry,routes:Mapping[str,str]):
        missing=set(self.REQUIRED)-routes.keys()
        if missing:raise ShortDramaProviderBindingError(f"missing provider routes: {sorted(missing)}")
        self.registry=registry;self.routes=dict(routes)
    def _invoke(self,capability:str,inputs:Mapping[str,Any])->Any:return self.registry.invoke(self.routes[capability],capability,inputs).output
    def generate(self,capability:str,inputs:Mapping[str,Any]):
        output=self._invoke(capability,inputs)
        if capability in {"short_drama.outline","short_drama.script","short_drama.storyboard"}:
            if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("text provider output must be an object")
            return output
        if not isinstance(output,Sequence) or isinstance(output,(str,bytes)):raise ShortDramaProviderBindingError("media provider output must be an array")
        values=[]
        for item in output:
            if not isinstance(item,Mapping):raise ShortDramaProviderBindingError("media item is invalid")
            values.append(ProviderOutput(item["content"],item["media_type"],item["source_id"],item.get("asset_kind","shot"),item.get("start_ms",0),item.get("end_ms",1)))
        return tuple(values)
    def compose(self,inputs:Mapping[str,Sequence[bytes]])->DeliveryOutput:
        output=self._invoke("short_drama.composition",inputs)
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("composition output is invalid")
        return DeliveryOutput(output["content"],output["media_type"])
    def review(self,content:bytes,media_type:str)->ReviewDecision:
        output=self._invoke("short_drama.review",{"content":content,"media_type":media_type})
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("review output is invalid")
        return ReviewDecision(output.get("approved") is True,tuple(output.get("issues",())))
    def repair(self,content:bytes,media_type:str,issues:tuple[str,...])->DeliveryOutput:
        output=self._invoke("short_drama.composition",{"content":content,"media_type":media_type,"issues":issues,"operation":"repair"})
        if not isinstance(output,Mapping):raise ShortDramaProviderBindingError("repair output is invalid")
        return DeliveryOutput(output["content"],output["media_type"])
