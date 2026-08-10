import subprocess,sys,unittest
from pathlib import Path
class SupplyChainGateTest(unittest.TestCase):
 def test_committed_sbom_matches_locked_dependencies(self):
  root=Path(__file__).resolve().parents[2];result=subprocess.run([sys.executable,str(root/"scripts/security/supply_chain_gate.py"),"--verify"],cwd=root,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr+result.stdout)
if __name__=="__main__":unittest.main()
