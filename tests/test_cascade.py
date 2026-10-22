import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cascade import moderate
class Cascade(unittest.TestCase):
 def test_big_model_adapter_injection_without_truth(self):
  class Fake:
   calls=0
   def review(self,text,policy):
    self.calls+=1;return {'decision':'block','risk':'offensive','confidence':.95,'reason':'synthetic fixture','provenance':'api'}
  a=Fake();p={'version':'synthetic-test','pass_threshold':.2,'block_threshold':.8}
  self.assertEqual(moderate('fixture',.1,0,p,a)['stage'],'lightweight');self.assertEqual(a.calls,0)
  self.assertEqual(moderate('fixture',.5,0,p,a)['stage'],'llm');self.assertEqual(a.calls,1)
  self.assertEqual(moderate('fixture',.5,0,p)['decision'],'review')
