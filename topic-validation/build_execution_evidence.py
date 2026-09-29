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
target=ROOT/'meeting-demo'
(target/'execution-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
