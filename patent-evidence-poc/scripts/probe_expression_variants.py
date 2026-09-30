"""Small retrospective expression diagnostic, no citation injection.
Freeze title-derived variants before reading citation labels. Three previously
inspected IDs remain a diagnostic, never an independent performance estimate.
"""
import json
import hashlib
import os
import sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items
from scripts.evaluate_real_pilot import normalized_document

def main():
    raw=ROOT/'data'/'raw'
    manifest=json.loads((raw/'query_candidate_manifest.json').read_text(encoding='utf-8'))
    variants={'오브젝트':['객체','물체'],'거리측정':['거리 측정']}
    plan={number:{'base':manifest['cases'][number]['searches'],'variants':sorted({variant for s in manifest['cases'][number]['searches'] for variant in variants.get(s['word'],[])})} for number in sorted(manifest['cases'])[:3]}
    plan={n:p for n,p in plan.items() if p['variants']}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            if key.strip() in ('KIPRIS_API_KEY','KIPRIS_ACCESS_KEY'):os.environ.setdefault(key.strip(),value.strip().strip('\"').strip("'"))
    report={'run_at':datetime.now(timezone.utc).isoformat(),'policy':'title-word translation/spacing alternatives fixed before labels; first 500 per query; no positive injection','variants':variants,'cases':{},'limit':'Retrospective one-case diagnostic, query meaning needs human validation. More candidates may be irrelevant.'}
    client=KiprisClient.from_env()
    for number,policy in plan.items():
        documents={}
        query=parse_items((raw/f'{number}.publication.xml').read_text(encoding='utf-8'))[0]
        def add(xml):
            for row in parse_items(xml):
                doc=normalized_document(row)
                if doc['doc_id'] and doc['doc_id']!=number:documents[doc['doc_id']]=doc
        def eligible():return {d['doc_id'] for d in documents.values() if d['first_public_date'] and d['first_public_date']<=query['ApplicationDate']}
        for search in policy['base']:add((raw/search['cache']).read_text(encoding='utf-8'))
        baseline=eligible()
        failures=[]
        counts={}
        for word in policy['variants']:
            path=raw/('variant_'+hashlib.sha256(word.encode()).hexdigest()[:12]+'.xml')
            try:
                if not path.exists():path.write_text(client._publication_call('freeSearchInfo',word=word,patent='true',utility='true',docsStart='1',docsCount='500'),encoding='utf-8')
                xml=path.read_text(encoding='utf-8');counts[word]=len(parse_items(xml));add(xml)
            except Exception as error:failures.append({'word':word,'error_type':type(error).__name__})
        expanded=eligible()
        gold=set()
        for split in ('pilot','holdout'):
            linkage=json.loads((raw/f'{split}_document_linkage.json').read_text(encoding='utf-8'))
            for row in linkage['linkage']:
                if row['query_application_number']==number and row['match_count']==1 and row['published_before_query_filing']:gold.add(row['matched_application_number'])
        report['cases'][number]={'query_title':query['InventionName'],'base_terms':[s['word'] for s in policy['base']],'variant_rows':counts,'failures':failures,'citation_proxy_count':len(gold),'before':{'candidates':len(baseline),'covered_proxies':len(baseline & gold)},'after':{'candidates':len(expanded),'covered_proxies':len(expanded & gold)}}
    (ROOT/'output'/'expression_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
