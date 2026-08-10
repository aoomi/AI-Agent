import json,unittest
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
S=json.loads((Path(__file__).resolve().parents[2]/"shared/contracts/industry-agent.schema.json").read_text())
def errors(n,v):return list(Draft202012Validator({"$ref":f"#/$defs/{n}","$defs":S["$defs"]},format_checker=FormatChecker()).iter_errors(v))
class IndustryAgentContractTest(unittest.TestCase):
 def test_industry_process_skill_robot_and_topology(self):
  cases={"industry":{"industry_id":"short-drama","display_name":"短剧","template_version":"1.0","metadata":{},"contract_version":"1.0"},"process":{"process_id":"outline","industry_id":"short-drama","display_name":"大纲","input_schema":{},"output_schema":{},"contract_version":"1.0"},"skill":{"skill_id":"outline-skill","process_id":"outline","manifest_version":"1.0","required_capabilities":["chat"],"permissions":["workspace.read"],"entrypoint":"skills/outline.py","contract_version":"1.0"},"robot":{"robot_id":"robot-1","skill_id":"outline-skill","tenant_id":"t","project_id":"p","model_id":"m","configuration_version":1,"status":"idle","created_at":"2026-08-07T12:00:00Z","contract_version":"1.0"},"workflow":{"workflow_id":"w","industry_id":"short-drama","robot_ids":["r1","r2"],"edges":[{"source_robot_id":"r1","target_robot_id":"r2","condition":None}],"mode":"serial","configuration_version":1,"contract_version":"1.0"}}
  for n,v in cases.items():self.assertFalse(errors(n,v),n)
 def test_unsafe_skill_entrypoint_and_duplicate_robots_fail(self):
  self.assertTrue(errors("skill",{"skill_id":"s","process_id":"p","manifest_version":"1","required_capabilities":["chat"],"permissions":[],"entrypoint":"../../x","contract_version":"1.0"}));self.assertTrue(errors("workflow",{"workflow_id":"w","industry_id":"i","robot_ids":["r","r"],"edges":[],"mode":"serial","configuration_version":1,"contract_version":"1.0"}))
if __name__=="__main__":unittest.main()
