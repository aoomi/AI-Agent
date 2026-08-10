import io,unittest
from ai_agent_events import MetricsRegistry,ObservabilityError,StructuredLogger,TraceRecorder
class ObservabilityTest(unittest.TestCase):
 def test_logs_metrics_and_traces(self):
  sink=io.StringIO();self.assertEqual(StructuredLogger(sink).emit("info","task.completed",{"task_id":"x"})["event"],"task.completed");metrics=MetricsRegistry();metrics.increment("tasks",labels=(("status","completed"),));self.assertEqual(next(iter(metrics.snapshot()["counters"].values())),1);traces=TraceRecorder()
  with traces.span("trace","span","task"):pass
  self.assertEqual(traces.spans[0].status,"ok")
 def test_secret_log_fields_are_rejected(self):
  with self.assertRaises(ObservabilityError):StructuredLogger(io.StringIO()).emit("info","x",{"api_key":"secret"})
if __name__=="__main__":unittest.main()
