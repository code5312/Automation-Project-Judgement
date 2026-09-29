"""Compare first 500 vs first 1500 results for 3 preselected query IDs.
Selection is sorted application number, never missed-label selection.
Raw responses remain gitignored. This diagnostic is not a holdout evaluation.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.xmlutil import parse_items
from scripts.evaluate_real_pilot import normalized_document

def main():
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            if key.strip() in ('KIPRIS_API_KEY','KIPRIS_ACCESS_KEY'):
                os.environ.setdefault(key.strip(),value.strip().strip('\"').strip("'"))
    raw=ROOT/'data'/'raw'
    manifest=json.loads((raw/'query_candidate_manifest.json').read_text(encoding='utf-8'))
    selected=sorted(manifest['cases'])[:3]
    # Freeze IDs and search terms before looking at evaluation labels.
    plan={number:manifest['cases'][number]['searches'] for number in selected}
    client=KiprisClient.from_env()
    collected={}
    calls=0
    for number,searches in plan.items():
        query=parse_items((raw/f'{number}.publication.xml').read_text(encoding='utf-8'))[0]
        documents={}
        stages=[]
        for start in (1,501,1001):
            counts=[]
            for search in searches:
                if start==1:
                    path=raw/search['cache']
                else:
                    digest=hashlib.sha256(search['word'].encode()).hexdigest()[:10]
                    path=raw/f'page_probe_{number}_{digest}_{start}.xml'
                    if not path.exists():
                        for attempt in range(3):
                            try:
                                xml=client._publication_call('freeSearchInfo',word=search['word'],patent='true',utility='true',docsStart=str(start),docsCount='500')
                                break
                            except Exception as error:
                                if attempt==2:
                                    failure={'status':'failed','selection':selected,'failed_query':number,'failed_start':start,'error_type':type(error).__name__,'completed_cases':collected,'limit':'Page expansion incomplete; no improvement conclusion.'}
                                    (ROOT/'output'/'page_probe.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
                                    print(json.dumps(failure))
                                    return
                                time.sleep(1)
                        path.write_text(xml,encoding='utf-8')
                        calls+=1
                rows=parse_items(path.read_text(encoding='utf-8'))
                counts.append(len(rows))
                for row in rows:
                    doc=normalized_document(row)
                    if doc['doc_id'] and doc['doc_id']!=number:
                        documents[doc['doc_id']]=doc
            eligible={doc['doc_id'] for doc in documents.values() if doc['first_public_date'] and doc['first_public_date']<=query['ApplicationDate']}
            stages.append({'through_result':start+499,'page_rows':counts,'unique_candidates':len(documents),'time_eligible_ids':sorted(eligible)})
        collected[number]={'search_terms':[s['word'] for s in searches],'stages':stages}
    gold={}
    for split in ('pilot','holdout'):
        linkage=json.loads((raw/f'{split}_document_linkage.json').read_text(encoding='utf-8'))
        for row in linkage['linkage']:
            if row['query_application_number'] in selected and row['match_count']==1 and row['published_before_query_filing']:
                gold.setdefault(row['query_application_number'],set()).add(row['matched_application_number'])
    for number,case in collected.items():
        case['citation_proxy_count']=len(gold[number])
        for stage in case['stages']:
            ids=set(stage.pop('time_eligible_ids'))
            stage['time_eligible_candidates']=len(ids)
            stage['covered_citation_proxies']=len(ids & gold[number])
    report={'selection':'first 3 sorted application IDs, fixed before label access','positive_injection':False,'new_api_calls':calls,'cases':collected,'limit':'Small diagnostic on previously inspected positive-citation cases; no general performance claim.'}
    (ROOT/'output'/'page_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':
    main()
