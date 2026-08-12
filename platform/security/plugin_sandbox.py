"""Brokered plugin file, process, network and tenant-data isolation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Mapping,Sequence
from urllib.parse import urlparse
class PluginSandboxError(PermissionError):pass
@dataclass(frozen=True,slots=True)
class PluginSandboxPolicy:
 plugin_id:str;tenant_id:str;plugin_root:Path;data_root:Path;writable:bool=False;allowed_hosts:frozenset[str]=frozenset();allowed_executables:frozenset[str]=frozenset()
class PluginSandboxBroker:
 def __init__(self,policy:PluginSandboxPolicy):
  if not isinstance(policy,PluginSandboxPolicy):raise PluginSandboxError("plugin sandbox policy is invalid")
  if any(not isinstance(value,str) or not value.strip() for value in (policy.plugin_id,policy.tenant_id)):raise PluginSandboxError("plugin sandbox identity is required")
  if not isinstance(policy.plugin_root,Path) or not isinstance(policy.data_root,Path):raise PluginSandboxError("plugin sandbox roots are invalid")
  if not isinstance(policy.writable,bool):raise PluginSandboxError("plugin sandbox writable must be boolean")
  if not isinstance(policy.allowed_hosts,frozenset) or not isinstance(policy.allowed_executables,frozenset):raise PluginSandboxError("plugin sandbox allowlist is invalid")
  if any(not isinstance(value,str) or not value.strip() for value in (*policy.allowed_hosts,*policy.allowed_executables)):raise PluginSandboxError("plugin sandbox allowlist is invalid")
  self.policy=policy
 def resolve_plugin_file(self,relative:str,*,write:bool=False)->Path:
  if not isinstance(write,bool):raise PluginSandboxError("plugin write control is invalid")
  if write and not self.policy.writable:raise PluginSandboxError("plugin filesystem is read-only")
  return self._inside(self.policy.plugin_root,relative)
 def resolve_data_file(self,relative:str,*,write:bool=False)->Path:
  if not isinstance(write,bool):raise PluginSandboxError("plugin write control is invalid")
  root=self.policy.data_root/self.policy.tenant_id/self.policy.plugin_id
  if write and not self.policy.writable:raise PluginSandboxError("plugin data is read-only")
  return self._inside(root,relative)
 def validate_network(self,url:str)->str:
  if not isinstance(url,str) or not url.strip():raise PluginSandboxError("plugin network destination is not authorized")
  parsed=urlparse(url)
  if (parsed.scheme!="https" or not parsed.hostname or parsed.hostname not in self.policy.allowed_hosts or parsed.username or parsed.password
      or parsed.fragment or parsed.port not in (None,443)):raise PluginSandboxError("plugin network destination is not authorized")
  return url
 def run_process(self,command:Sequence[str],*,timeout_seconds:int=30)->subprocess.CompletedProcess[bytes]:
  if not isinstance(command,(list,tuple)) or not command or any(not isinstance(value,str) or not value for value in command) or command[0] not in self.policy.allowed_executables:raise PluginSandboxError("plugin executable is not authorized")
  if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,int) or timeout_seconds<1 or timeout_seconds>300:raise PluginSandboxError("plugin process timeout is invalid")
  return subprocess.run(tuple(command),cwd=self.policy.plugin_root,env={"PATH":"/usr/bin:/bin"},stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout_seconds,check=False)
 @staticmethod
 def _inside(root:Path,relative:str)->Path:
  if not isinstance(relative,str) or not relative.strip() or Path(relative).is_absolute():raise PluginSandboxError("plugin path is invalid")
  root=root.resolve();target=(root/relative).resolve()
  if not target.is_relative_to(root):raise PluginSandboxError("plugin path escapes sandbox")
  return target
