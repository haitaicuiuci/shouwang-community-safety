import sys,tempfile,threading,json,urllib.request,urllib.error,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import serve
from common import ROOT,dump
checks={}
original_ops=serve.OPER
with serve.connect_ops() as c:before_events=c.execute('SELECT COUNT(*) FROM events').fetchone()[0]
with tempfile.TemporaryDirectory() as d:
 serve.OPER=Path(d)/'qa-only-operations.sqlite'
 server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler);port=server.server_port;base=f'http://127.0.0.1:{port}'
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def get(path):
  with urllib.request.urlopen(base+path) as r:return r.status,r.read()
 def post(v,origin=None):
  req=urllib.request.Request(base+'/api/action',data=json.dumps(v).encode(),headers={'Content-Type':'application/json','Origin':origin or base})
  with urllib.request.urlopen(req) as r:return json.loads(r.read())
 try:
  status,html=get('/');checks['root_http_200']=status==200
  data=json.loads(get('/data.json')[1]);checks['real_dashboard_test_count']=data['routing']['n']==5311
  expected_queue=data['routing']['counts']['review']
  q=json.loads(get('/api/queue')[1]);sid=q['items'][0]['sample_id'];checks['queue_matches_current_experiment_no_labels']=q['total']==expected_queue and expected_queue>0 and all(set(x)=={'sample_id','priority','reason'} for x in q['items'])
  checks['text_reveal_endpoint']=bool(json.loads(get('/api/text?id='+sid)[1])['text'])
  for path in ['/artifacts/warehouse.sqlite','/data/raw/test.csv','/../README.md']:
   try:get(path);checks['deny_'+path]=False
   except urllib.error.HTTPError as e:checks['deny_'+path]=e.code==404
  v={'id':sid,'kind':'review','decision':'pass','reviewer':'QA-only','reason':'仅隔离环境接口测试，无实际人工判定'}
  checks['isolated_post_review']=post(v)['ok'] and json.loads(get('/api/queue')[1])['total']==expected_queue-1
  v.update(kind='appeal',decision='review');checks['isolated_appeal_requeue']=post(v)['ok'] and json.loads(get('/api/queue')[1])['total']==expected_queue
  try:post(v,'https://untrusted.invalid');checks['cross_origin_rejected']=False
  except urllib.error.HTTPError as e:checks['cross_origin_rejected']=e.code==403
  try:
   urllib.request.urlopen(urllib.request.Request(base+'/',headers={'Host':'untrusted.invalid'}));checks['host_rejected']=False
  except urllib.error.HTTPError as e:checks['host_rejected']=e.code==403
 finally:server.shutdown();server.server_close();thread.join()
with sqlite3.connect(ROOT/'artifacts/operations.sqlite') as c:checks['actual_human_events_unchanged']=c.execute('SELECT COUNT(*) FROM events').fetchone()[0]==before_events
assert all(checks.values()),checks
dump(ROOT/'artifacts/http_verification.json',{'checks':checks,'all_passed':True,'human_event_test_isolation':'Temporary SQLite deleted after test; no actual human review completed'})
print(json.dumps(checks,ensure_ascii=False,indent=2))
