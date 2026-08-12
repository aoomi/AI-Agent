import tempfile,unittest
from pathlib import Path
from ai_agent_security import PluginSandboxBroker,PluginSandboxError,PluginSandboxPolicy
class PluginSandboxTest(unittest.TestCase):
 def test_policy_and_process_runtime_contracts_are_rejected(self):
  root=Path(self.tmp.name)
  for policy in (object(),PluginSandboxPolicy("","tenant",root,root),PluginSandboxPolicy(1,"tenant",root,root),PluginSandboxPolicy("plugin","tenant","root",root),PluginSandboxPolicy("plugin","tenant",root,root,writable=1),PluginSandboxPolicy("plugin","tenant",root,root,allowed_hosts=[])):
   with self.subTest(policy=policy),self.assertRaises(PluginSandboxError):PluginSandboxBroker(policy)
  for command,timeout in (("/usr/bin/true",30),(("/usr/bin/true",),True)):
   with self.subTest(command=command,timeout=timeout),self.assertRaises(PluginSandboxError):self.broker.run_process(command,timeout_seconds=timeout)
  for call in (lambda:self.broker.resolve_plugin_file(1),lambda:self.broker.resolve_data_file("x",write=1),lambda:self.broker.validate_network(1)):
   with self.subTest(call=call),self.assertRaises(PluginSandboxError):call()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);(root/"plugin").mkdir();self.broker=PluginSandboxBroker(PluginSandboxPolicy("plugin","tenant",root/"plugin",root/"data",True,frozenset({"api.example.com"}),frozenset({"/usr/bin/true"})))
 def tearDown(self):self.tmp.cleanup()
 def test_scoped_files_data_network_and_process(self):
  self.assertTrue(str(self.broker.resolve_plugin_file("assets/a.txt",write=True)).endswith("plugin/assets/a.txt"));self.assertIn("tenant/plugin",str(self.broker.resolve_data_file("x.json",write=True)));self.assertEqual(self.broker.validate_network("https://api.example.com/v1"),"https://api.example.com/v1");self.assertEqual(self.broker.run_process(("/usr/bin/true",)).returncode,0)
 def test_escape_unlisted_host_and_process_are_denied(self):
  for call in (lambda:self.broker.resolve_plugin_file("../../secret"),lambda:self.broker.validate_network("https://evil.example"),lambda:self.broker.run_process(("/bin/sh","-c","id"))):
   with self.assertRaises(PluginSandboxError):call()
if __name__=="__main__":unittest.main()
