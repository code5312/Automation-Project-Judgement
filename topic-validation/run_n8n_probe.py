"""Execute real n8n HTTP Request workflows against an isolated local CRM.
Usage: python run_n8n_probe.py <absolute n8n bin/n8n path> [node executable]
Inputs are synthetic. Four workflows test two orders before/after field split.
Runtime/database stays outside source control. No credentials are needed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent

def main():
    binary=Path(sys.argv[1]).resolve()
    node_binary=sys.argv[2] if len(sys.argv)>2 else 'node'
    output=ROOT/'output'/'n8n-probe'
    output.mkdir(parents=True,exist_ok=True)
    report={'run_at':datetime.now(timezone.utc).isoformat(),'expected_version':'2.41.3','kind':'real n8n HTTP Request nodes / synthetic CRM','runs':[],'limit':'Sequential workflow ordering only; no concurrent scheduler or production CRM.'}
    if not binary.is_file():
        report.update({'status':'failed','error_type':'MissingRuntime'})
        (ROOT/'output'/'n8n-probe.json').write_text(json.dumps(report),encoding='utf-8')
        return 1
    with tempfile.TemporaryDirectory(prefix='u3-n8n-crm-') as temporary:
        state_file=Path(temporary)/'customer.json'
        lock=threading.Lock()
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def respond(self,value):
                body=json.dumps(value).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                with lock:
                    state={'status':'new'} if self.path=='/reset' else json.loads(state_file.read_text())
                    if self.path!='/reset':state.update(data)
                    state_file.write_text(json.dumps(state))
                    requests.append({'method':'POST','path':self.path,'body':data})
                self.respond(state)
            def do_GET(self):
                requests.append({'method':'GET','path':self.path})
                self.respond(json.loads(state_file.read_text()))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        env=os.environ.copy()
        env.update({'N8N_USER_FOLDER':str(output/'runtime'),'N8N_DIAGNOSTICS_ENABLED':'false','N8N_VERSION_NOTIFICATIONS_ENABLED':'false','N8N_TEMPLATES_ENABLED':'false','N8N_RUNNERS_ENABLED':'false','N8N_LOG_LEVEL':'error'})
        env.pop('KIPRIS_API_KEY',None);env.pop('KIPRIS_ACCESS_KEY',None)
        def command(args,name):
            report['last_step']=name
            result=subprocess.run([node_binary,str(binary),*args],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            (output/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            if result.returncode:raise RuntimeError('n8n command failed; see local log')
        try:
            report['node_version']=subprocess.run([node_binary,'--version'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
            dependency=subprocess.run([node_binary,'-e',"require(require.resolve('sqlite3',{paths:[process.argv[1]]}))",str(binary.parent.parent)],capture_output=True,timeout=15)
            if dependency.returncode:raise RuntimeError('SQLite native dependency unavailable')
            report['sqlite_dependency']='load verified'
            version=subprocess.run([node_binary,str(binary),'--version'],env=env,capture_output=True,text=True,timeout=60)
            if version.returncode:raise RuntimeError('Cannot read runtime version')
            report['runtime_version']=version.stdout.strip()
            assert report['runtime_version']==report['expected_version']
            for fixed in (False,True):
                for order in (('marketing','cs'),('cs','marketing')):
                    key=('fixed' if fixed else 'shared')+'-'+ '-'.join(order)
                    workflow_id='u3'+key.replace('-','')
                    nodes=[{'id':'start','name':'Start','type':'n8n-nodes-base.manualTrigger','typeVersion':1,'position':[0,0],'parameters':{}}]
                    connections={}
                    actions=[('Reset','POST','/reset',{}),*[(flow,'POST','/update',{(flow+'_status' if fixed else 'status'):'nurturing' if flow=='marketing' else 'support_pending'}) for flow in order],('Read','GET','/state',None)]
                    previous='Start'
                    for index,(name,method,path,body) in enumerate(actions,1):
                        parameters={'method':method,'url':url+path,'options':{}}
                        if body is not None:parameters.update({'sendBody':True,'specifyBody':'json','jsonBody':json.dumps(body)})
                        nodes.append({'id':name,'name':name,'type':'n8n-nodes-base.httpRequest','typeVersion':4.2,'position':[index*240,0],'parameters':parameters})
                        connections[previous]={'main':[[{'node':name,'type':'main','index':0}]]};previous=name
                    workflow={'id':workflow_id,'name':key,'active':False,'nodes':nodes,'connections':connections,'settings':{'executionOrder':'v1'}}
                    path=output/(key+'.json');path.write_text(json.dumps(workflow),encoding='utf-8')
                    command(['import:workflow','--input='+str(path)],key+'-import')
                    requests.clear()
                    command(['execute','--id='+workflow_id],key+'-execute')
                    state=json.loads(state_file.read_text())
                    expected={'status':'new','marketing_status':'nurturing','cs_status':'support_pending'} if fixed else {'status':'support_pending' if order[-1]=='cs' else 'nurturing'}
                    assert state==expected
                    assert [r['path'] for r in requests]==['/reset','/update','/update','/state']
                    assert requests[1]['body']==actions[1][3] and requests[2]['body']==actions[2][3]
                    report['runs'].append({'separate_fields':fixed,'order':order,'persisted_state':state,'expected_state':expected,'http_trace':list(requests),'workflow_file':path.name,'execution_log':key+'-execute.log'})
            report['status']='verified'
            report.pop('last_step',None)
        except Exception as error:
            report.update({'status':'failed','error_type':type(error).__name__})
            if isinstance(error,subprocess.TimeoutExpired):
                report['failure_reason']='CLI did not finish within its 120-second limit.'
                def decode(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
                partial=decode(error.stdout)+decode(error.stderr)
                (output/'timeout.log').write_text(partial,encoding='utf-8')
        finally:
            server.shutdown();server.server_close();thread.join()
    (ROOT/'output'/'n8n-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='verified' else 1

if __name__=='__main__':raise SystemExit(main())
