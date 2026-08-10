from __future__ import annotations
import json, unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA=json.loads((Path(__file__).resolve().parents[2]/"shared/contracts/provider.schema.json").read_text())
def errors(name,value): return list(Draft202012Validator({"$ref":f"#/$defs/{name}","$defs":SCHEMA["$defs"]},format_checker=FormatChecker()).iter_errors(value))
NOW="2026-08-07T12:00:00Z"

class ProviderContractTest(unittest.TestCase):
    def configuration(self):
        return {"provider_id":"openai-main","display_name":"OpenAI","kind":"model","endpoint":"https://api.example.com/v1","secret_reference":"vault://providers/openai","capabilities":["chat","structured_output"],"enabled":True,"timeout_seconds":60,"rate_limit":{"requests_per_minute":120,"concurrent_requests":8},"settings":{"organization":"org-1"},"created_at":NOW,"updated_at":NOW,"contract_version":"1.0"}
    def test_valid_configuration_and_health(self):
        self.assertFalse(errors("configuration",self.configuration()))
        self.assertFalse(errors("health",{"provider_id":"openai-main","status":"healthy","checked_at":NOW,"latency_ms":82,"error_code":None,"consecutive_failures":0,"circuit_open_until":None,"contract_version":"1.0"}))
    def test_inline_secrets_and_insecure_endpoints_are_rejected(self):
        self.assertTrue(errors("configuration",{**self.configuration(),"secret_reference":"sk-live-secret"}))
        self.assertTrue(errors("configuration",{**self.configuration(),"endpoint":"http://api.example.com"}))
        self.assertTrue(errors("configuration",{**self.configuration(),"settings":{"api_key":"secret"}}))
    def test_healthy_state_cannot_retain_failure_state(self):
        health={"provider_id":"p","status":"healthy","checked_at":NOW,"latency_ms":1,"error_code":"TIMEOUT","consecutive_failures":1,"circuit_open_until":NOW,"contract_version":"1.0"}
        self.assertTrue(errors("health",health))

if __name__=="__main__": unittest.main()
