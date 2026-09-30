"""Publish sanitized, saved execution evidence; never copy API credentials."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
report=json.loads((ROOT/'output'/'execution-poc.json').read_text(encoding='utf-8'))
trace=json.loads((ROOT/'output'/'external-trace-results.json').read_text(encoding='utf-8'))
report['external_trace']={k:v for k,v in trace.items() if k!='rows'}
patent=ROOT.parent/'patent-evidence-poc'/'output'
report['patent_baseline']=json.loads((patent/'candidate_generation.json').read_text(encoding='utf-8'))['summary']['all']
if (patent/'page_probe.json').exists():
    report['patent_page_probe']=json.loads((patent/'page_probe.json').read_text(encoding='utf-8'))
if (patent/'expression_probe.json').exists():
    report['patent_expression_probe']=json.loads((patent/'expression_probe.json').read_text(encoding='utf-8'))
if (ROOT/'output'/'n8n-probe.json').exists():
    report['n8n_probe']=json.loads((ROOT/'output'/'n8n-probe.json').read_text(encoding='utf-8'))
if (ROOT/'output'/'public-cases.json').exists():
    report['public_cases']=json.loads((ROOT/'output'/'public-cases.json').read_text(encoding='utf-8'))
if (ROOT/'output'/'data-access.json').exists():
    report['data_access']=json.loads((ROOT/'output'/'data-access.json').read_text(encoding='utf-8'))
target=ROOT/'meeting-demo'
(target/'execution-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
