"""Deterministic Chinese LoRA matching and project-version locking."""
from __future__ import annotations
from dataclasses import dataclass
import random
class LoraSelectionError(ValueError):pass
@dataclass(frozen=True,slots=True)
class LoraDefinition:lora_id:str;version:str;genres:frozenset[str];display_name:str
@dataclass(frozen=True,slots=True)
class LoraSelection:mode:str;drama_genre:str;selected_lora_id:str;selected_lora_version:str;locked:bool;match_reason:str;exploration_seed:int|None
class LoraSelectionService:
 def __init__(self,catalog:tuple[LoraDefinition,...]):
  if not catalog:raise LoraSelectionError("LoRA catalog is empty")
  self.catalog=tuple(sorted(catalog,key=lambda x:(x.lora_id,x.version)));self.locks={}
 def select(self,tenant_id:str,project_id:str,genre:str,*,mode:str="automatic",lora_id:str|None=None,exploration_seed:int|None=None,override:bool=False)->LoraSelection:
  key=(tenant_id,project_id)
  if key in self.locks and not override:return self.locks[key]
  matches=[item for item in self.catalog if genre in item.genres] or list(self.catalog)
  if mode=="exploration":
   if exploration_seed is None:raise LoraSelectionError("exploration mode requires seed")
   selected=random.Random(exploration_seed).choice(matches);locked=False;reason="seeded exploration"
  elif mode in {"fixed","manual"}:
   selected=next((item for item in self.catalog if item.lora_id==lora_id),None)
   if selected is None:raise LoraSelectionError("selected LoRA does not exist")
   locked=True;reason=f"{mode} selection"
  elif mode=="automatic":selected=matches[0];locked=True;reason="deterministic genre match" if genre in selected.genres else "deterministic catalog fallback"
  else:raise LoraSelectionError("LoRA selection mode is invalid")
  result=LoraSelection(mode,genre,selected.lora_id,selected.version,locked,reason,exploration_seed if mode=="exploration" else None)
  if locked:self.locks[key]=result
  return result
