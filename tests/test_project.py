import sys,unittest,tempfile,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,sha,redact,normalize
from adapter import ReviewAdapter
from pipeline import route
class Integrity(unittest.TestCase):
 def test_sources(self):
  m=json.loads((ROOT/'data/source_manifest.json').read_text())
  for i in m['files']:self.assertEqual(sha((ROOT/'data/raw'/i['file']).read_bytes()),i['sha256'])
 def test_no_leakage_and_accounting(self):
  with sqlite3.connect(ROOT/'artifacts/warehouse.sqlite') as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM (SELECT normalized_hash FROM samples GROUP BY normalized_hash HAVING COUNT(DISTINCT split)>1)').fetchone()[0],0)
   r=json.loads((ROOT/'artifacts/results.json').read_text());self.assertEqual(c.execute('SELECT COUNT(*) FROM samples').fetchone()[0]+c.execute('SELECT COUNT(*) FROM quality_exclusions').fetchone()[0],r['quality']['raw_total'])
   self.assertEqual(sum(r['routing']['counts'].values()),r['routing']['n'])
   self.assertEqual(c.execute('SELECT COUNT(*) FROM review_queue').fetchone()[0],r['routing']['counts']['review'])
   self.assertEqual(c.execute("SELECT COUNT(*) FROM predictions WHERE strategy='cascade' AND decision='review' AND prediction IS NOT NULL").fetchone()[0],0)
 def test_truth_is_not_human(self):
  with sqlite3.connect(ROOT/'artifacts/warehouse.sqlite') as c:self.assertNotIn('source_label',[r[1] for r in c.execute('PRAGMA table_info(review_queue)')])
  with sqlite3.connect(ROOT/'artifacts/adapter_audit.sqlite') as c:
   self.assertEqual(c.execute("SELECT COUNT(*) FROM audit WHERE event!='disabled'").fetchone()[0],0)
 def test_normalize_redact(self):
  self.assertEqual(normalize('Ａ b，Ｃ!'),normalize('abc'))
  s=redact('@测试 https://example.com 13812345678 a@b.com');self.assertNotIn('13812345678',s);self.assertNotIn('example.com',s)
 def test_route_boundaries(self):
  self.assertEqual(route(.2,0,.2,.8),'pass');self.assertEqual(route(.2,1,.2,.8),'review');self.assertEqual(route(.8,0,.2,.8),'block')
class Adapter(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'audit.db'
 def tearDown(self):self.tmp.cleanup()
 def test_disabled(self):
  a=ReviewAdapter(self.path);self.assertEqual(a.review('synthetic fixture')['provenance'],'disabled');a.db.close()
 def test_cache_and_policy_version(self):
  calls=[]
  def transport(t,timeout):calls.append(t);return dict(decision='pass',risk='safe',confidence=.9,reason='fixture only')
  a=ReviewAdapter(self.path,'https://example.invalid',transport=transport)
  self.assertEqual(a.review('fixture')['provenance'],'api');self.assertEqual(a.review('fixture')['provenance'],'cache');a.review('fixture','v2');self.assertEqual(len(calls),2);a.db.close()
 def test_timeout_and_invalid_schema_fail_closed(self):
  for mode in ['timeout','invalid']:
   calls=[]
   def transport(t,timeout):
    calls.append(timeout)
    if mode=='timeout':raise TimeoutError()
    return {'decision':'pass'}
   a=ReviewAdapter(self.path,'https://example.invalid',transport=transport,retries=2,timeout=.01)
   self.assertEqual(a.review(mode)['provenance'],'fallback');self.assertEqual(len(calls),3);a.db.close()
 def test_inconsistent_and_nan(self):
  for v in [dict(decision='block',risk='safe',confidence=.9,reason='x'),dict(decision='pass',risk='safe',confidence=float('nan'),reason='x')]:
   with self.assertRaises(ValueError):ReviewAdapter.validate(v)
if __name__=='__main__':unittest.main()
