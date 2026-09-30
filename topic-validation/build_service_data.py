"""Build public data inventory for working browser services; no credentials exported."""
import json,re,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
PATENT=ROOT.parent/'patent-evidence-poc'
sys.path.insert(0,str(PATENT))
from src.patent_evidence.xmlutil import parse_items

def main():
    rows=json.loads((ROOT/'output/data-access/swe-rows.json').read_text(encoding='utf-8'))['rows']
    descriptions=[('중첩 모델의 분리 행렬 계산 오류','중첩된 CompoundModel에서 독립 입력의 분리 여부가 잘못 계산됩니다.','separability_matrix CompoundModel nested'),('RST 표 출력의 헤더 행 지원','ascii.rst 출력에서 header_rows 인자를 지원하지 않아 오류가 발생합니다.','ascii.rst header_rows RestructuredText'),('QDP 명령의 소문자 인식 오류','QDP 명령을 대문자로만 인식해 read serr 입력이 실패합니다.','ascii.qdp read serr lowercase')]
    incidents=[]
    for entry,(title,summary,tags) in zip(rows,descriptions):
        row=entry['row']
        incidents.append({'id':row['instance_id'],'title':title,'summary':summary,'keywords':tags,'paths':re.findall(r'^diff --git a/(.+?) b/',row['patch'],re.M),'tests':json.loads(row['FAIL_TO_PASS']) if isinstance(row['FAIL_TO_PASS'],str) else row['FAIL_TO_PASS'],'base':row['base_commit'],'source':'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite','repository':row['repo'],'limit':'공개 수정·테스트 기록. 이 앱에서 원본 테스트를 재실행하지 않았습니다.'})
    probe=json.loads((ROOT/'output/n8n-probe.json').read_text(encoding='utf-8'))
    full=json.loads((ROOT/'output/n8n-probe/shared-marketing-cs.json').read_text(encoding='utf-8'))
    flows=[]
    for name in ['marketing','cs']:
        node=next(n for n in full['nodes'] if n['name']==name)
        node['parameters']['url']='https://crm.example.test/customers/demo'
        flows.append({'name':name,'nodes':[node],'connections':{}})
    raw=PATENT/'data/raw'
    manifest=json.loads((raw/'query_candidate_manifest.json').read_text(encoding='utf-8'))
    caches=[s['cache'] for s in manifest['cases']['1020110127749']['searches']]
    caches+=sorted(p.name for p in raw.glob('variant_*.xml'))
    patents={}
    for filename in caches:
        for item in parse_items((raw/filename).read_text(encoding='utf-8')):
            number=item.get('ApplicationNumber')
            if not number:continue
            patents[number]={'id':number,'title':item.get('InventionName',''),'abstract':item.get('Abstract','')[:3500],'ipc':item.get('InternationalpatentclassificationNumber',''),'publicDate':item.get('OpeningDate') or item.get('PublicDate',''),'applicationDate':item.get('ApplicationDate',''),'applicant':item.get('Applicant',''),'source':'KIPRIS 성공 조회 캐시'}
    project={'name':'배송 정책 작업 사본','kind':'controlled','artifacts':[
        {'path':'policy.md','content':'일반 고객은 주문 금액 5만원 이상이면 무료배송입니다.','scope':'general'},
        {'path':'faq.md','content':'오만 원 이상 주문하면 배송비를 받지 않습니다.','scope':'general'},
        {'path':'cs.md','content':'배송비 면제는 결제 합계가 오만 원일 때부터 적용됩니다.','scope':'general'},
        {'path':'shipping.json','content':json.dumps({'freeShippingMinimum':50000,'shippingFee':3000},ensure_ascii=False),'scope':'config'},
        {'path':'tests.json','content':json.dumps([{'amount':50000,'expectedFee':0}]),'scope':'tests'},
        {'path':'vip.md','content':'VIP 고객은 금액과 무관하게 무료배송입니다.','scope':'unrelated'},
        {'path':'payment.json','content':'{"maxPayment":50000}','scope':'unrelated'}]}
    execution=json.loads((ROOT/'output/execution-poc.json').read_text(encoding='utf-8'))
    data={'generatedAt':datetime.now(timezone.utc).isoformat(),'incidents':incidents,'flows':flows,'workflowSource':'실행한 n8n 워크플로에서 HTTP 노드 추출. URL은 example.test로 치환.','n8nEvidence':{'status':probe['status'],'runs':len(probe['runs']),'version':probe['runtime_version']},'publicWorkflow':json.loads((ROOT/'output/data-access/public-workflow.json').read_text(encoding='utf-8')),'project':project,'sdk':execution['topics']['d'],'patents':list(patents.values()),'patentScope':{'terms':['거리측정','오브젝트','객체','물체','거리 측정'],'cacheFiles':len(caches),'live':False}}
    (ROOT/'meeting-demo/service-data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'incidents':len(incidents),'patents':len(patents),'sdkFiles':len(data['sdk']['files'])}))

if __name__=='__main__':main()
