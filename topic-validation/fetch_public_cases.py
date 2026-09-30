"""Collect public issue/fix and code/test change evidence without private data.
No third-party code is executed. CI success is recorded as upstream evidence,
not as a test run performed by U3. These cases are references, not gold labels.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from run_execution_poc import external_json

ROOT=Path(__file__).resolve().parent

def pull_case(number):
    api=f'https://api.github.com/repos/n8n-io/n8n/pulls/{number}'
    pr=external_json(api)
    files=external_json(api+'/files?per_page=100')
    checks=external_json(f"https://api.github.com/repos/n8n-io/n8n/commits/{pr['head']['sha']}/check-runs?per_page=100")
    return {'url':pr['html_url'],'title':pr['title'],'merged':pr['merged'],'base_sha':pr['base']['sha'],'head_sha':pr['head']['sha'],'merge_sha':pr['merge_commit_sha'],'changed_files_reported':pr['changed_files'],'files_complete':len(files)==pr['changed_files'],'files':[{'path':f['filename'],'status':f['status'],'additions':f['additions'],'deletions':f['deletions'],'patch_available':bool(f.get('patch'))} for f in files],'checks':[{'name':c['name'],'conclusion':c['conclusion'],'url':c['html_url']} for c in checks['check_runs']],'checks_total':checks['total_count'],'checks_complete':len(checks['check_runs'])==checks['total_count'],'limit':'Upstream metadata only. PR merge/CI is not independent reproduction or a reusable business remedy label.'}

def main():
    report={'run_at':datetime.now(timezone.utc).isoformat(),'cases':{}}
    for key,number in (('retry_fix',8480),('shared_storage_conflict',25541)):
        try:
            report['cases'][key]=pull_case(number)
        except Exception as error:
            report['cases'][key]={'status':'failed','error_type':type(error).__name__}
    issue=external_json('https://api.github.com/repos/n8n-io/n8n/issues/25066')
    report['reported_failure']={'url':issue['html_url'],'state':issue['state'],'title':issue['title'],'limit':'Reported operational failure; reported frequency is not U3 measured performance.'}
    report['conclusions']={
        'b1':'Public bugs and fixes supply failure description and developer action, but lack per-order human remedy success records. Automatic mapping rule learning remains unvalidated.',
        'b2':'Shared storage conflict exists in a public automation implementation. This is different from CRM business rule conflicts and does not replace executing real workflows.',
        'b3':'Public PRs supply exact versions and changed code/test paths. Changed file list is an observed change set, not the complete set of files that ought to change.',
        'd':'Public SDK changes do not contain private IP decision premises. No reviewed IP event labels obtained.'}
    path=ROOT/'output'/'public-cases.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:{'merged':value.get('merged'),'files':len(value.get('files',[])),'failed':value.get('status')=='failed'} for key,value in report['cases'].items()}))

if __name__=='__main__':
    main()
