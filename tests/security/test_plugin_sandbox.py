import tempfile,unittest
from pathlib import Path
from ai_agent_security import PluginSandboxBroker,PluginSandboxError,PluginSandboxPolicy
class PluginSandboxTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);(root/"plugin").mkdir();self.broker=PluginSandboxBroker(PluginSandboxPolicy("plugin","tenant",root/"plugin",root/"data",True,frozenset({"api.example.com"}),frozenset({"/usr/bin/true"})))
 def tearDown(self):self.tmp.cleanup()
 def test_scoped_files_data_network_and_process(self):
  self.assertTrue(str(self.broker.resolve_plugin_file("assets/a.txt",write=True)).endswith("plugin/assets/a.txt"));self.assertIn("tenant/plugin",str(self.broker.resolve_data_file("x.json",write=True)));self.assertEqual(self.broker.validate_network("https://api.example.com/v1"),"https://api.example.com/v1");self.assertEqual(self.broker.run_process(("/usr/bin/true",)).returncode,0)
 def test_escape_unlisted_host_and_process_are_denied(self):
  for call in (lambda:self.broker.resolve_plugin_file("../../secret"),lambda:self.broker.validate_network("https://evil.example"),lambda:self.broker.run_process(("/bin/sh","-c","id"))):
   with self.assertRaises(PluginSandboxError):call()
if __name__=="__main__":unittest.main()
