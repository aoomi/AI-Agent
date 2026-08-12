import io,json,tempfile,unittest
from pathlib import Path
from ai_agent_events import (AlertEvaluator,AlertRule,CompositeExporter,JsonLinesExporter,
 MetricsRegistry,ObservabilityError,PrometheusSnapshotExporter,StructuredLogger,TraceRecorder)
class ObservabilityTest(unittest.TestCase):
 def test_runtime_observability_contracts_are_rejected(self):
  for build in (lambda:CompositeExporter((object(),)),lambda:StructuredLogger(object()),lambda:MetricsRegistry(object()),lambda:TraceRecorder(clock=None),lambda:AlertEvaluator((AlertRule("","metric",1),)),lambda:AlertEvaluator((AlertRule("alert","metric",True),))):
   with self.subTest(build=build),self.assertRaises(ObservabilityError):build()
  with self.assertRaises(ObservabilityError):StructuredLogger(io.StringIO()).emit("","event",{})
  with self.assertRaises(ObservabilityError):
   with TraceRecorder().span("trace","span","",attributes=[]):pass
  for operation in (lambda:CompositeExporter(1),lambda:JsonLinesExporter("/tmp/unused").export(1,{}),lambda:StructuredLogger(io.StringIO()).emit(1,"event",{}),lambda:MetricsRegistry().increment(1),lambda:TraceRecorder().span(1,"span","name").__enter__(),lambda:AlertEvaluator((object(),)),lambda:AlertEvaluator(()).evaluate([])):
   with self.subTest(operation=operation),self.assertRaises(ObservabilityError):operation()
 def test_logs_metrics_and_traces(self):
  sink=io.StringIO();self.assertEqual(StructuredLogger(sink).emit("info","task.completed",{"task_id":"x"})["event"],"task.completed");metrics=MetricsRegistry();metrics.increment("tasks",labels=(("status","completed"),));self.assertEqual(next(iter(metrics.snapshot()["counters"].values())),1);traces=TraceRecorder()
  with traces.span("trace","span","task"):pass
  self.assertEqual(traces.spans[0].status,"ok")
 def test_secret_log_fields_are_rejected(self):
  with self.assertRaises(ObservabilityError):StructuredLogger(io.StringIO()).emit("info","x",{"api_key":"secret"})
  with self.assertRaises(ObservabilityError):StructuredLogger(io.StringIO()).emit("info","x",{"nested":{"authorization":"secret"}})
  for fields in ({"prompt":"商业核心提示"},{"message":"Bearer abcdefghijklmnop"},{"value":"13800138000"},{"credential":"opaque"}):
   with self.assertRaises(ObservabilityError):StructuredLogger(io.StringIO()).emit("info","x",fields)
  self.assertEqual(StructuredLogger(io.StringIO()).emit("info","x",{"message":"completed 138 tasks"})["event"],"x")
 def test_durable_exporters_and_correlation(self):
  with tempfile.TemporaryDirectory() as directory:
   events=Path(directory)/"events.jsonl";metrics_file=Path(directory)/"metrics.prom"
   exporter=CompositeExporter((JsonLinesExporter(events),PrometheusSnapshotExporter(metrics_file)))
   sink=io.StringIO();StructuredLogger(sink,exporter).emit("info","task.completed",{"request_id":"req-1","trace_id":"tr-1","task_id":"job-1"})
   metrics=MetricsRegistry(exporter);metrics.increment("tasks_total",labels=(("status","failed"),));metrics.gauge("queue_depth",7,labels=(("pool","accelerator"),))
   snapshot=metrics.export_snapshot(request_id="req-1",trace_id="tr-1")
   self.assertEqual(snapshot["request_id"],"req-1");self.assertIn('queue_depth{pool="accelerator"} 7',metrics_file.read_text())
   traces=TraceRecorder(clock=iter((1.0,1.125)).__next__,exporter=exporter)
   with traces.span("tr-1","span-1","provider",request_id="req-1",attributes={"provider_id":"p"}):pass
   records=[json.loads(line) for line in events.read_text().splitlines()]
   self.assertEqual([record["kind"] for record in records],["log","metrics_snapshot","span"])
   self.assertEqual(records[-1]["duration_ms"],125)
 def test_alert_evaluation_exports_failure_with_correlation(self):
  with tempfile.TemporaryDirectory() as directory:
   events=Path(directory)/"alerts.jsonl";exporter=JsonLinesExporter(events);metrics=MetricsRegistry()
   metrics.gauge("queue_oldest_seconds",301,labels=(("pool","accelerator"),))
   evaluator=AlertEvaluator((AlertRule("queue_stuck","queue_oldest_seconds",300,labels=(("pool","accelerator"),)),),exporter)
   alerts=evaluator.evaluate(metrics.structured_snapshot(),request_id="req-2",trace_id="tr-2")
   self.assertEqual(alerts[0]["alert"],"queue_stuck")
   persisted=json.loads(events.read_text());self.assertEqual(persisted["kind"],"alert");self.assertEqual(persisted["trace_id"],"tr-2")
 def test_metric_labels_are_canonical_and_counters_monotonic(self):
  metrics=MetricsRegistry();metrics.increment("requests_total",labels=(("status",200),("route","health")))
  metrics.increment("requests_total",labels=(("route","health"),("status",200)))
  self.assertEqual(next(iter(metrics.snapshot()["counters"].values())),2)
  with self.assertRaises(ObservabilityError):metrics.increment("requests_total",-1)
  for invalid in (float("nan"),float("inf"),float("-inf"),"1",True):
   with self.assertRaises(ObservabilityError):metrics.increment("requests_total",invalid)
   with self.assertRaises(ObservabilityError):metrics.gauge("queue_depth",invalid)
  with self.assertRaises(ObservabilityError):metrics.gauge("queue_depth",1,labels=(("bad-key","x"),))
 def test_sensitive_metric_labels_cannot_reach_any_persistent_exporter(self):
  with tempfile.TemporaryDirectory() as directory:
   events=Path(directory)/"events.jsonl";prometheus=Path(directory)/"metrics.prom"
   metrics=MetricsRegistry(JsonLinesExporter(events))
   with self.assertRaises(ObservabilityError):metrics.gauge("provider_state",1,labels=(("authorization","TOP-SECRET"),))
   self.assertFalse(events.exists())
   crafted={"timestamp":"now","counters":[],"gauges":[{"name":"provider_state","labels":[["api_token","TOP-SECRET"]],"value":1}]}
   with self.assertRaises(ObservabilityError):JsonLinesExporter(events).export("metrics_snapshot",crafted)
   with self.assertRaises(ObservabilityError):PrometheusSnapshotExporter(prometheus).export("metrics_snapshot",crafted)
   for invalid in (
    {"counters":[{"name":"requests_total","labels":[],"value":float("nan")}],"gauges":[]},
    {"counters":[{"name":"requests_total","labels":[["bad-key","x"]],"value":1}],"gauges":[]},
    {"counters":[{"name":"bad-name","labels":[],"value":1}],"gauges":[]},
   ):
    with self.assertRaises(ObservabilityError):JsonLinesExporter(events).export("metrics_snapshot",invalid)
    with self.assertRaises(ObservabilityError):PrometheusSnapshotExporter(prometheus).export("metrics_snapshot",invalid)
   self.assertFalse(events.exists());self.assertFalse(prometheus.exists())
 def test_secret_values_cannot_bypass_exporter_with_neutral_keys(self):
  with tempfile.TemporaryDirectory() as directory:
   events=Path(directory)/"events.jsonl";prometheus=Path(directory)/"metrics.prom"
   for exporter in (JsonLinesExporter(events),PrometheusSnapshotExporter(prometheus)):
    with self.assertRaises(ObservabilityError):exporter.export("metrics_snapshot",{"counters":[],"gauges":[{"name":"state","labels":[["value","github_pat_abcdefghijklmnop"]],"value":1}]})
   self.assertFalse(events.exists());self.assertFalse(prometheus.exists())
if __name__=="__main__":unittest.main()
