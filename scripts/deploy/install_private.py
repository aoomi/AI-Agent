#!/usr/bin/env python3
from __future__ import annotations
import argparse,shutil,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument("--check-only",action="store_true");p.add_argument("--health-url",default="http://127.0.0.1:8080/health");a=p.parse_args()
 for command in ("docker",):
  if shutil.which(command) is None:raise SystemExit(f"MISSING_DEPENDENCY:{command}")
 if a.check_only:return
 env=ROOT/"deploy/environments/private-production.env"
 if not env.exists():raise SystemExit("PRIVATE_PRODUCTION_ENV_MISSING")
 subprocess.run(["docker","compose","-f",str(ROOT/"deploy/docker/compose.private.yaml"),"up","-d","--build"],check=True)
 for _ in range(30):
  try:
   with urllib.request.urlopen(a.health_url,timeout=3) as response:
    if response.status==200:return
  except OSError:time.sleep(2)
 raise SystemExit("HEALTH_CHECK_FAILED")
if __name__=="__main__":main()
