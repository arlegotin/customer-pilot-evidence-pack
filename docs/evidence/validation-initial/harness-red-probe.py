import sys,tempfile,unittest,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from support import *
from test_corruptions import state_errors
from pilotpack import schema
class Probe(unittest.TestCase):
 def test_disabled_hash_diagnostic_is_detected(self):
  with tempfile.TemporaryDirectory() as t:
   # Disabling the intended diagnostic only in this throwaway process.
   original=schema._diagnostic
   schema._diagnostic=lambda code,*a,**kw: original('DISABLED_DIAGNOSTIC' if code=='HASH_MISMATCH' else code,*a,**kw)
   result=evaluate_validation_input(apply_mutation(ROOT/'fixtures/controls/parent','C01',Path(t)/'input'))
   case=json.loads((ROOT/'fixtures/corruptions/manifest.json').read_text())['cases'][0]
   self.assertEqual(state_errors(result,case),[])
unittest.main()
