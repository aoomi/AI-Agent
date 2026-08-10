#!/usr/bin/env python3
"""Verify dependency locks and emit a deterministic CycloneDX SBOM."""
from __future__ import annotations
import argparse,json,re,tomllib
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def build():
 uv=ROOT/"uv.lock";pnpm=ROOT/"frontend/pnpm-lock.yaml";policy=json.loads((ROOT/"deploy/supply-chain-policy.json").read_text())
 if not uv.exists() or not pnpm.exists():raise SystemExit("DEPENDENCY_LOCK_MISSING")
 py=tomllib.loads(uv.read_text());components=[]
 for p in py.get("package",[]):components.append({"type":"library","name":p["name"],"version":p["version"],"purl":f"pkg:pypi/{p['name']}@{p['version']}"})
 text=pnpm.read_text()
 for name,version in sorted(set(re.findall(r"^\s{2}([^\s/][^:]*?)@([^:()]+):$",text,re.M))):components.append({"type":"library","name":name,"version":version,"purl":f"pkg:npm/{name}@{version}"})
 denied={(x["name"],x["version"]) for x in policy["denied_components"]}
 bad=[c for c in components if (c["name"],c["version"]) in denied]
 if bad:raise SystemExit("VULNERABLE_DEPENDENCY_DENIED")
 return {"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"metadata":{"component":{"type":"application","name":"ai-agent-platform","version":"0.1.0"},"properties":[{"name":"uv.lock.sha256","value":sha256(uv.read_bytes()).hexdigest()},{"name":"pnpm-lock.yaml.sha256","value":sha256(pnpm.read_bytes()).hexdigest()}]},"components":sorted(components,key=lambda x:(x["purl"]))}
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--verify",action="store_true");args=parser.parse_args();content=json.dumps(build(),ensure_ascii=False,sort_keys=True,indent=2)+"\n";target=ROOT/"deploy/sbom.cdx.json"
 if args.verify:
  if not target.exists() or target.read_text()!=content:raise SystemExit("SBOM_OUT_OF_DATE")
 else:target.write_text(content)
if __name__=="__main__":main()
