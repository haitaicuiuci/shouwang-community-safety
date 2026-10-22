"""Loopback-only dashboard. Static allowlist, label-blind review queue, persistent human actions."""
import argparse,json,sqlite3,time,uuid
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from common import ROOT,redact
ART=ROOT/'artifacts'; OPER=ART/'operations.sqlite'
def connect_ops():
    c=sqlite3.connect(OPER)
    c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, sample_id TEXT, kind TEXT, decision TEXT, reviewer TEXT, reason TEXT, created_at REAL)')
    c.commit();return c
def sample_exists(sid):
    with sqlite3.connect(ART/'warehouse.sqlite') as c:return c.execute("SELECT 1 FROM samples WHERE id=? AND split='test'",(sid,)).fetchone() is not None
def record_event(sid,kind,decision,reviewer,reason):
    if not sample_exists(sid):raise ValueError('Unknown test sample')
    if kind not in ('review','appeal') or decision not in ('pass','block','review'):raise ValueError('Invalid action')
    if not 1<=len(reviewer)<=80 or not 8<=len(reason)<=500:raise ValueError('请填写审核人，并提供 8–500 字的依据')
    with connect_ops() as c:c.execute('INSERT INTO events(sample_id,kind,decision,reviewer,reason,created_at) VALUES(?,?,?,?,?,?)',(sid,kind,decision,reviewer,reason,time.time()))
def queue_payload():
    with sqlite3.connect(ART/'warehouse.sqlite') as c:
        c.row_factory=sqlite3.Row;items={r['sample_id']:dict(r) for r in c.execute('SELECT sample_id,priority,reason FROM review_queue ORDER BY priority DESC')}
    with connect_ops() as c:
        c.row_factory=sqlite3.Row;events=[dict(r) for r in c.execute('SELECT * FROM events ORDER BY id')]
    latest={e['sample_id']:e for e in events}
    for sid,e in latest.items():
        if e['kind']=='appeal' or e['decision']=='review':items[sid]={'sample_id':sid,'priority':1.,'reason':'appeal' if e['kind']=='appeal' else 'needs_context'}
        else:items.pop(sid,None)
    return {'items':sorted(items.values(), key=lambda x:x['priority'],reverse=True),'total':len(items),'completed':sum(e['kind']=='review' and e['decision']!='review' for e in latest.values())}

class Handler(BaseHTTPRequestHandler):
    def reply(self,v,status=200):
        b=json.dumps(v,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.headers.get('Host','') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
            return self.reply({'error':'Host rejected'},403)
        u=urlparse(self.path)
        if u.path=='/api/queue':
            return self.reply(queue_payload())
        if u.path=='/api/text':
            sid=parse_qs(u.query).get('id',[''])[0]
            with sqlite3.connect(ART/'warehouse.sqlite') as c:row=c.execute("SELECT text FROM samples WHERE id=? AND split='test'",(sid,)).fetchone()
            return self.reply({'text':redact(row[0]),'notice':'已处理链接、账号、邮箱与长数字；人名和间接身份信息不保证消除。仅限本地研究。'} if row else {'error':'not found'},200 if row else 404)
        if u.path=='/api/activity':
            with connect_ops() as c:
                c.row_factory=sqlite3.Row;return self.reply([dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100')])
        allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/data.json':'data.json'}
        if u.path not in allowed:return self.reply({'error':'not found'},404)
        p=ROOT/'dashboard'/allowed[u.path];b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',{'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'}[p.suffix]);self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:");self.end_headers();self.wfile.write(b)
    def do_POST(self):
        origin=self.headers.get('Origin','');expected='http://'+self.headers.get('Host','')
        if origin!=expected or not self.headers.get('Host','').startswith(('127.0.0.1:','localhost:')):return self.reply({'error':'Origin rejected'},403)
        if self.path!='/api/action':return self.reply({'error':'not found'},404)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=4096:raise ValueError('Invalid size')
            p=json.loads(self.rfile.read(size));record_event(p['id'],p['kind'],p.get('decision','review'),p['reviewer'],p['reason']);return self.reply({'ok':True})
        except (ValueError,KeyError,TypeError) as e:return self.reply({'error':str(e)},400)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);args=p.parse_args();connect_ops().close()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Local: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
