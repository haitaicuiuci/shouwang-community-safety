"""Synthetic workflow events in a temporary DB; never written into actual human audit."""
import sys,unittest,tempfile,sqlite3
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import serve
class Operations(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.patcher=patch.object(serve,'OPER',Path(self.tmp.name)/'ops.sqlite');self.patcher.start()
  self.initial=serve.queue_payload();self.sid=self.initial['items'][0]['sample_id']
 def tearDown(self):self.patcher.stop();self.tmp.cleanup()
 def test_review_appeal_and_recheck(self):
  serve.record_event(self.sid,'review','pass','QA-fixture','测试夹具通过，不属于真实审核')
  self.assertEqual(serve.queue_payload()['total'],self.initial['total']-1)
  serve.record_event(self.sid,'appeal','review','QA-fixture','测试夹具申诉，不属于真实申诉')
  self.assertEqual(serve.queue_payload()['total'],self.initial['total'])
  self.assertEqual(serve.queue_payload()['items'][0]['reason'],'appeal')
  serve.record_event(self.sid,'review','block','QA-fixture','测试夹具再审，不属于真实审核')
  self.assertEqual(serve.queue_payload()['completed'],1)
  with serve.connect_ops() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM events').fetchone()[0],3)
 def test_pending_and_rejected_actions(self):
  serve.record_event(self.sid,'review','review','QA-fixture','需要上下文的合成状态流转测试')
  self.assertEqual(serve.queue_payload()['total'],self.initial['total'])
  with self.assertRaises(ValueError):serve.record_event('unknown','review','pass','qa','这是无效样本验证测试')
  with self.assertRaises(ValueError):serve.record_event(self.sid,'review','other','qa','这是非法结论验证测试')
 def test_queue_has_no_truth_or_text(self):
  for row in self.initial['items']:self.assertEqual(set(row),{'sample_id','priority','reason'})
