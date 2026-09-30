"""Bounded public-source acquisition checks; no private business data assumed.
Stores third-party inputs locally (gitignored), publishes only inventory facts.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'output'/'data-access'
FETCHED={}

def acquire(name,url):
    with urlopen(Request(url,headers={'User-Agent':'U3-data-access-probe','Accept':'application/json'}),timeout=25) as response:
        body=response.read(2_000_001)
    if len(body)>2_000_000:raise ValueError('Bounded download limit exceeded')
    (RAW/name).write_bytes(body)
    FETCHED[name]={'source_url':url,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
    return body

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'sources':{},'limit':'Public software evidence and controlled executions are not private company business records.'}
    def check(key,fn):
        try:report['sources'][key]={'status':'acquired',**fn()}
        except Exception as error:report['sources'][key]={'status':'failed','error_type':type(error).__name__}
    def swe():
        url='https://datasets-server.huggingface.co/rows?'+urlencode({'dataset':'princeton-nlp/SWE-bench_Lite','config':'default','split':'test','offset':0,'length':3})
        data=json.loads(acquire('swe-rows.json',url))
        required=['instance_id','problem_statement','patch','test_patch','base_commit','FAIL_TO_PASS','PASS_TO_PASS']
        rows=data['rows']
        assert len(rows)==3 and all(all(field in row['row'] for field in required) for row in rows)
        return {'url':'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite','sample_count':len(rows),'fields':required,'ids':[row['row']['instance_id'] for row in rows],'test_execution':'not performed','usable_for':'Failure/repair/test-record schema and software issue retrieval proxy','missing':'Order input, operator correction reason, business outcome labels'}
    def workflow():
        url='https://raw.githubusercontent.com/n8n-io/self-hosted-ai-starter-kit/refs/heads/main/n8n/demo-data/workflows/srOnR8PAY3u4RSwb.json'
        data=json.loads(acquire('public-workflow.json',url))
        assert isinstance(data['nodes'],list) and isinstance(data['connections'],dict)
        return {'url':url,'nodes':len(data['nodes']),'node_types':sorted({n['type'] for n in data['nodes']}),'connection_sources':len(data['connections']),'credential_references':sum(bool(n.get('credentials')) for n in data['nodes']),'usable_for':'Parse real workflow nodes, parameters and graph','missing':'Public execution history and business conflict ground truth; referenced services require separate credentials'}
    def libest():
        base=ROOT/'output/external/finegrained-traceability/datasets/LibEST'
        links=(base/'req_to_code_ground.txt').read_text(encoding='utf-8').splitlines()
        return {'url':'https://github.com/tobhey/finegrained-traceability/tree/197cf2f395e9e90636436f30d6383465cb9e9f63/datasets/LibEST','requirements':len(list((base/'req').glob('*'))),'code_files':len(list((base/'code').glob('*'))),'trace_rows':len([l for l in links if l.strip()]),'usable_for':'Requirements-to-code retrieval using supplied links','missing':'Before/after policy change, complete expected change set and business completion labels','reuse':'Repository GPL-3.0; original dataset attribution separate; raw corpus stays local'}
    def license_record():
        url='https://api.github.com/repos/getsentry/self-hosted/contents/LICENSE.md'
        meta=json.loads(acquire('license-meta.json',url))
        content=acquire('license.txt',meta['download_url']).decode('utf-8')
        return {'url':meta['html_url'],'blob_sha':meta['sha'],'header':content.splitlines()[0],'has_patent_section':'Patent' in content,'decision_publication':'https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding/','usable_for':'Public license decision statement and exact current license artifact','missing':'Internal disclosure premises, reviewer decisions, IP-event ground truth','scope':'Self-hosted Sentry; do not apply this license to Python SDK or infer legal conclusions'}
    def patent():
        paths=sorted((ROOT.parent/'patent-evidence-poc/data/raw').glob('*.publication.xml'))
        assert paths
        fields=set()
        for path in paths[:3]:
            tree=ET.fromstring(path.read_text(encoding='utf-8'))
            fields.update(e.tag for e in tree.iter() if e.text and e.text.strip())
        return {'sample_files':min(3,len(paths)),'available_fields':sorted(fields),'source':'Existing authenticated KIPRIS successful response cache','usable_for':'Document IDs, public dates, title, abstract and classification retrieval; exact fields above','missing':'Human relevance/novelty/infringement labels; full-text availability must be checked by operation','access':'Existing approved API key; approval and call limits depend on service; do not publish key/raw cache'}
    check('b1_software_proxy',swe)
    check('b2_public_definition',workflow)
    check('b3_trace_dataset',libest)
    check('d_public_license_record',license_record)
    check('patent_actual_fields',patent)
    report['download_manifest']=FETCHED
    (ROOT/'output/data-access.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
