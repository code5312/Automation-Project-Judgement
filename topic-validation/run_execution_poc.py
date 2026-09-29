"""Executable feasibility probes, separate from the browser simulation.

B1/B2 use real loopback HTTP writes to SQLite with controlled synthetic inputs.
B3 edits real files and executes a shipping function in an isolated directory.
D fetches public SDK release metadata; it cannot validate IP judgments.
Patent fetches KIPRIS using the existing adapter without printing credentials.
"""
from __future__ import annotations
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PATENT = ROOT.parent / 'patent-evidence-poc'

def external_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'U3-feasibility-poc', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def local_probes():
    with tempfile.TemporaryDirectory(prefix='u3-poc-') as temporary:
        base = Path(temporary)
        db = base / 'service.sqlite'
        with closing(sqlite3.connect(db)) as connection, connection:
            connection.executescript('CREATE TABLE customer(id INTEGER PRIMARY KEY,status TEXT,marketing_status TEXT,cs_status TEXT); CREATE TABLE orders(id TEXT PRIMARY KEY,sku TEXT);')
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                code, result = 200, {}
                with closing(sqlite3.connect(db)) as connection, connection:
                    if self.path == '/customer/reset':
                        connection.execute('DELETE FROM customer')
                        connection.execute("INSERT INTO customer VALUES(1,'new',NULL,NULL)")
                    elif self.path == '/customer/update':
                        field = data['field']
                        if field not in ('status','marketing_status','cs_status'):
                            code, result = 400, {'error':'unsupported field'}
                        else:
                            connection.execute(f'UPDATE customer SET {field}=? WHERE id=1',(data['value'],))
                    elif self.path == '/order':
                        if data.get('sku') not in ('CUP350','CUP500'):
                            code, result = 422, {'error':'mapping missing'}
                        else:
                            old = connection.execute('SELECT sku FROM orders WHERE id=?',(data['id'],)).fetchone()
                            if old and old[0] != data['sku']:
                                code, result = 409, {'error':'idempotency conflict'}
                            else:
                                connection.execute('INSERT OR IGNORE INTO orders VALUES(?,?)',(data['id'],data['sku']))
                                result = {'accepted':True,'sku':data['sku']}
                    else:
                        code, result = 404, {'error':'unknown path'}
                body = json.dumps(result).encode()
                self.send_response(code)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        def post(path, data):
            request = urllib.request.Request(url+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(request,timeout=5) as response:
                    return {'http':response.status,'body':json.load(response)}
            except urllib.error.HTTPError as error:
                return {'http':error.code,'body':json.load(error)}
        try:
            # Historical human correction is supplied, not inferred from labels.
            history = {'channel':'mall','code':'cup-350','volume':350,'sku':'CUP350'}
            failure = post('/order',{'id':'order-1','sku':None})
            repaired = post('/order',{'id':'order-1','sku':history['sku']})
            retry = post('/order',{'id':'order-1','sku':history['sku']})
            conflict = post('/order',{'id':'order-1','sku':'CUP500'})
            new_inputs = [{'channel':'mall','code':'cup-350','volume':350}, {'channel':'mall','code':'cup-350','volume':500}, {'channel':'other','code':'cup-350','volume':350}]
            matching = [all(item[k]==history[k] for k in ('channel','code','volume')) for item in new_inputs]
            with closing(sqlite3.connect(db)) as connection, connection:
                count = connection.execute('SELECT count(*) FROM orders').fetchone()[0]
            assert failure['http']==422 and repaired['http']==200 and retry['http']==200 and conflict['http']==409 and count==1 and matching==[True,False,False]
            b1 = {'kind':'controlled synthetic inputs / real HTTP and SQLite execution','failure':failure,'human_corrected_replay':repaired,'same_retry':retry,'conflicting_retry':conflict,'persisted_orders':count,'new_input_rule_matches':matching,'limit':'No production remedy history; reuse rule supplied by experiment author.'}
            runs = []
            for fixed in (False,True):
                for order in (('marketing','cs'),('cs','marketing')):
                    post('/customer/reset',{})
                    events=[]
                    for flow in order:
                        value = 'nurturing' if flow=='marketing' else 'support_pending'
                        field = (flow+'_status') if fixed else 'status'
                        events.append({'flow':flow,'write':{field:value},'response':post('/customer/update',{'field':field,'value':value})})
                    with closing(sqlite3.connect(db)) as connection, connection:
                        state = connection.execute('SELECT status,marketing_status,cs_status FROM customer').fetchone()
                    runs.append({'separate_fields':fixed,'order':order,'events':events,'database_result':state})
            assert runs[0]['database_result'] != runs[1]['database_result']
            assert runs[2]['database_result'] == runs[3]['database_result']
            b2 = {'kind':'controlled automation client / real HTTP and SQLite execution','runs':runs,'limit':'Sequential ordering experiment, not concurrent scheduling or n8n execution. Field separation only tested for this supplied policy.'}
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        project = base / 'shipping-project'
        project.mkdir()
        (project/'shipping.py').write_text('THRESHOLD = 50000\ndef free_shipping(total):\n    return total >= THRESHOLD\n',encoding='utf-8')
        for name in ('policy.md','faq.md','cs.md'):
            (project/name).write_text('일반 고객 5만원 이상 무료배송',encoding='utf-8')
        (project/'vip.md').write_text('VIP 금액 무관 무료배송',encoding='utf-8')
        def inspect():
            namespace={}
            exec(compile((project/'shipping.py').read_text(),str(project/'shipping.py'),'exec'),namespace)
            cases=[{'total':amount,'expected':expected,'actual':namespace['free_shipping'](amount)} for amount,expected in ((29999,False),(30000,True),(50000,True))]
            stale=[name for name in ('policy.md','faq.md','cs.md') if '5만원' in (project/name).read_text(encoding='utf-8')]
            return {'executed_boundary_cases':cases,'stale_documents':stale,'complete':all(c['expected']==c['actual'] for c in cases) and not stale}
        before=inspect()
        (project/'shipping.py').write_text((project/'shipping.py').read_text().replace('50000','30000'),encoding='utf-8')
        for name in ('policy.md','faq.md'):
            (project/name).write_text('일반 고객 3만원 이상 무료배송',encoding='utf-8')
        partial=inspect()
        (project/'cs.md').write_text('일반 고객 3만원 이상 무료배송',encoding='utf-8')
        corrected=inspect()
        assert not before['complete'] and not partial['complete'] and partial['stale_documents']==['cs.md'] and corrected['complete']
        assert partial['executed_boundary_cases'][2]['actual'] is True
        b3={'kind':'controlled project / actual file mutation and executable function','before':before,'partial':partial,'corrected':corrected,'unrelated_vip_unchanged':(project/'vip.md').read_text(encoding='utf-8')=='VIP 금액 무관 무료배송','limit':'Known affected-file list; does not verify automatic dependency discovery in a real repository.'}
        return {'b1':b1,'b2':b2,'b3':b3}

def public_sdk_probe():
    releases=external_json('https://api.github.com/repos/getsentry/sentry-python/releases?per_page=5')
    usable=[r for r in releases if not r['draft'] and not r['prerelease']]
    if len(usable)<2:
        raise ValueError('Need two public stable releases')
    new,old=usable[:2]
    comparison=external_json(f"https://api.github.com/repos/getsentry/sentry-python/compare/{old['tag_name']}...{new['tag_name']}")
    files=[{'path':f['filename'],'status':f['status'],'additions':f['additions'],'deletions':f['deletions']} for f in comparison.get('files',[])]
    return {'kind':'live public GitHub SDK release metadata','repository':'getsentry/sentry-python','old_tag':old['tag_name'],'new_tag':new['tag_name'],'published_at':new['published_at'],'release_url':new['html_url'],'comparison_url':comparison['html_url'],'total_commits':comparison['total_commits'],'files':files,'source_digest':hashlib.sha256(json.dumps(comparison,sort_keys=True).encode()).hexdigest(),'review_signal':'public SDK release changed; no private premise record exists','ip_judgment_validated':False,'limit':'Public changes only. No company IP decisions, confidentiality facts, or ground truth. GitHub comparison may truncate large diffs.'}

def patent_probe():
    sys.path.insert(0,str(PATENT))
    from src.patent_evidence.kipris import KiprisClient
    # Load only named KIPRIS variables; do not execute or print the .env file.
    for line in (PATENT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name,value=line.split('=',1)
            if name.strip() in ('KIPRIS_API_KEY','KIPRIS_ACCESS_KEY'):
                os.environ.setdefault(name.strip(),value.strip().strip('\"').strip("'"))
    client=KiprisClient.from_env()
    rows=client.search_application('1020140170841')
    if len(rows)!=1:
        raise ValueError('Expected one publication')
    row=rows[0]
    return {'kind':'live KIPRIS API publication lookup','application_number':'1020140170841','matched_documents':len(rows),'title':row.get('InventionName'),'opening_date':row.get('OpeningDate'),'field_names':sorted(row),'limit':'Connectivity and metadata only; not a new retrieval quality evaluation.'}

def main():
    output=ROOT/'output'/'execution-poc.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'schema':'u3-execution-evidence-v1','run_at':datetime.now(timezone.utc).isoformat(),'topics':local_probes()}
    for key,operation in (('d',public_sdk_probe),('patent',patent_probe)):
        try:
            report['topics'][key]=operation()
        except Exception as error:
            # Avoid URLs or exception tracebacks that could contain API credentials.
            report['topics'][key]={'status':'failed','error_type':type(error).__name__,'limit':'Fetch not validated; do not substitute simulated success.'}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v.get('status','executed') for k,v in report['topics'].items()}))

if __name__=='__main__':
    main()
