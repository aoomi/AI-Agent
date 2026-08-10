import json,unittest
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
S=json.loads((Path(__file__).resolve().parents[2]/"shared/contracts/plugin-security.schema.json").read_text());V=Draft202012Validator({"$ref":"#/$defs/manifest","$defs":S["$defs"]},format_checker=FormatChecker())
def manifest():return {"plugin_id":"short-drama","plugin_version":"1.0.0","package_sha256":"a"*64,"signature":{"algorithm":"ed25519","key_id":"release-1","signature_base64":"A"*86+"==","signed_at":"2026-08-07T12:00:00Z","manifest_sha256":"b"*64},"source":{"kind":"repository","uri":"https://example.com/plugin.git","publisher_id":"official","retrieved_at":"2026-08-07T12:00:00Z","commit_sha":"c"*40},"sbom_format":"CycloneDX-1.5","components":[{"name":"runtime","version":"1.0.0","package_url":"pkg:pypi/runtime@1.0.0","sha256":"d"*64,"licenses":["MIT"],"dependencies":[]}],"minimum_platform_version":"1.0.0","generated_at":"2026-08-07T12:00:00Z","contract_version":"1.0"}
class PluginSecurityContractTest(unittest.TestCase):
 def test_valid(self):self.assertFalse(list(V.iter_errors(manifest())))
 def test_bad_hash_signature_source_and_empty_sbom_fail(self):
  for patch in ({"package_sha256":"x"},{"signature":{**manifest()["signature"],"algorithm":"none"}},{"source":{**manifest()["source"],"uri":"ftp://bad"}},{"components":[]}):self.assertTrue(list(V.iter_errors({**manifest(),**patch})))
if __name__=="__main__":unittest.main()
