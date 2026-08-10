from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime,timezone
import json,time
class ObservabilityError(ValueError):pass
class StructuredLogger:
 def __init__(self,sink):self.sink=sink
 def emit(self,level,event,fields):
  if any(any(w in str(k).lower() for w in ("secret","token","password","api_key","authorization")) for k in fields):raise ObservabilityError("log fields contain secrets")
  record={"timestamp":datetime.now(timezone.utc).isoformat(),"level":level,"event":event,**dict(fields)};self.sink.write(json.dumps(record,sort_keys=True)+"\n");return record
class MetricsRegistry:
 def __init__(self):self.counters={};self.gauges={}
 def increment(self,name,value=1,labels=()):self.counters[(name,labels)]=self.counters.get((name,labels),0)+value
 def gauge(self,name,value=0,labels=()):self.gauges[(name,labels)]=value
 def snapshot(self):return {"counters":dict(self.counters),"gauges":dict(self.gauges)}
@dataclass(frozen=True,slots=True)
class TraceSpan:trace_id:str;span_id:str;name:str;duration_ms:int;status:str
class TraceRecorder:
 def __init__(self,clock=time.monotonic):self.clock=clock;self.spans=[]
 @contextmanager
 def span(self,trace_id,span_id,name):
  start=self.clock();status="ok"
  try:yield
  except Exception:status="error";raise
  finally:self.spans.append(TraceSpan(trace_id,span_id,name,int((self.clock()-start)*1000),status))
