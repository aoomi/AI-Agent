from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from short_drama_workflows.langgraph_pipeline import ShortDramaLangGraphPipeline
from short_drama_workflows.pipeline import NODES,NodeOutput
class ShortDramaProductionTest(unittest.TestCase):
 def runners(self,fail_once=None):
  calls={}
  def make(node):
   def run(artifacts):
    calls[node]=calls.get(node,0)+1
    if node==fail_once and calls[node]==1:raise ConnectionError("transient")
    return NodeOutput(f"real-{node}".encode(),"application/octet-stream")
   return run
  return {node:make(node) for node in NODES},calls
 def test_langgraph_full_flow_retry_pause_restart_resume_and_export(self):
  with tempfile.TemporaryDirectory() as d:
   runners,calls=self.runners("video");root=Path(d);pipeline=ShortDramaLangGraphPipeline(root,runners);paused=pipeline.start("run-1",NodeOutput(b"requirements","application/json"));self.assertIn("__interrupt__",paused)
   restarted=ShortDramaLangGraphPipeline(root,runners);completed=paused
   while completed["status"]=="waiting_human": completed=restarted.resume("run-1",True)
   self.assertEqual(calls["video"],2);self.assertEqual(completed["status"],"completed");self.assertTrue((root/completed["artifacts"]["review_export"]).exists())
 def test_human_rejection_never_reports_success(self):
  with tempfile.TemporaryDirectory() as d:
   runners,_=self.runners();pipeline=ShortDramaLangGraphPipeline(Path(d),runners);pipeline.start("run-2",NodeOutput(b"r","application/json"));result=pipeline.resume("run-2",False);self.assertEqual(result["status"],"cancelled");self.assertNotIn("review_export",result["artifacts"])
 def test_artifact_manifest_rejects_non_string_or_unknown_entries(self):
  with tempfile.TemporaryDirectory() as d:
   runners,_=self.runners();pipeline=ShortDramaLangGraphPipeline(Path(d),runners);pipeline.start("run-3",NodeOutput(b"r","application/json"))
   manifest=Path(d)/"run-3"/"artifacts.json"
   for payload in ('{"requirements":NaN}','{"unknown":"unknown.bin"}','{"requirements":1}'):
    manifest.write_text(payload,encoding="utf-8")
    with self.subTest(payload=payload),self.assertRaisesRegex(Exception,"manifest not found or invalid"):pipeline.state("run-3")
if __name__=="__main__":unittest.main()
