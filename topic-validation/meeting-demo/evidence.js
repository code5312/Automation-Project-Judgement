const descriptions={
 b1:{name:'B-1 반복 예외',input:'통제된 주문 입력과 사람이 지정한 상품 매핑. 실제 고객 주문은 아닙니다.',execution:'로컬 HTTP 서버 → 상품 검증 → SQLite 저장 → 동일 주문 재시도.',result:'매핑 누락은 HTTP 422, 보정 후 200. 같은 주문 재시도는 DB 1건 유지, 다른 SKU 재시도는 409로 차단.',human:'재사용 규칙의 범위를 채널·상품코드·용량으로 제한합니다. 다른 용량과 채널은 보류합니다.',unknown:'실제 업무의 해결 이력에서 규칙을 발견하거나 현업 정확도를 측정한 것은 아닙니다.'},
 b2:{name:'B-2 자동화 충돌',input:'마케팅과 CS가 같은 고객 상태를 수정하는 통제된 두 자동화 클라이언트.',execution:'각 흐름이 실제 HTTP 업데이트를 보내고 SQLite 최종 상태를 읽었습니다.',result:'실행 순서 2가지의 최종 상태가 달랐습니다. 목적별 상태 필드를 분리하자 두 순서의 결과가 같았습니다.',human:'업무상 상태를 분리해도 되는지 결정합니다. 필드 분리가 모든 충돌의 해결책은 아닙니다.',unknown:'실제 n8n의 순차 HTTP 워크플로는 확인했습니다. 동시성·회사 자동화 정의와 업무 정답은 아직 확인하지 않았습니다.'},
 b3:{name:'B-3 변경 완료',input:'격리된 작은 배송 프로젝트의 실제 Python 코드·정책·FAQ·상담 파일.',execution:'파일을 실제 수정한 뒤 배송 함수를 실행하고 문서 잔존 값을 검사했습니다.',result:'코드·정책·FAQ만 변경하면 상담 문구가 남아 완료를 보류합니다. 보정 후 29,999·30,000·50,000원 검사와 문서 검사가 통과합니다.',human:'실제 프로젝트의 영향 범위와 완료 조건을 확인합니다.',unknown:'영향 파일 목록을 사전에 지정했습니다. 자동 영향 탐색의 검증은 별도 공개 데이터 검색 실험 수준입니다.'},
 d:{name:'D IP 사건 탐지',input:'GitHub의 Sentry Python SDK 공개 릴리스 2개와 변경 파일 메타데이터.',execution:'GitHub API에서 릴리스와 두 버전의 비교 결과를 조회했습니다.',result:'실제 공개 시점·버전·변경 파일을 가져오는 것은 가능했습니다. 이 변화가 IP 검토 대상인지 판단하는 것은 아직 미검증입니다.',human:'비공개 전제와 과거 판단 기록을 연결하고 재검토 필요성을 결정해야 합니다.',unknown:'공개 저장소에는 해당 회사의 IP 판단 기록이 없습니다. 모든 SDK 변경을 IP 사건으로 분류하지 않습니다.'},
 patent:{name:'특허 검색 보조',input:'기존 KIPRIS 키와 실제 공개 문헌, 기존 30개 질의의 인용 문헌 대용 평가자료.',execution:'KIPRIS 문헌 1건을 재조회하고 기존 캐시의 검색 평가를 재실행했습니다. 추가 페이지 검색은 별도 작은 진단입니다.',result:'문헌 조회는 성공했습니다. 기존 후보 확보는 77쌍 중 15쌍이며, 부족한 후보를 순위 조정만으로 회수할 수 없습니다.',human:'원문 근거와 기술 관계를 검토합니다. 인용 이력은 법적 정답이 아닙니다.',unknown:'새 검색 전략의 일반 성능·신규성·침해 여부를 검증하지 않았습니다.'}
};
const escapeText=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let evidence;
function expressionSummary(){
 const rows=Object.values(evidence.patent_expression_probe?.cases||{});
 if(!rows.length)return '표시할 진단 결과가 없습니다.';
 return rows.map(row=>{
  if(row.failures?.length)return '일부 표현 조회가 실패했습니다. 상세 기록의 오류와 확보된 범위를 확인하세요.';
  return `시점 조건을 만족하는 후보는 ${escapeText(row.before.candidates)}→${escapeText(row.after.candidates)}건, 인용 문헌 회수는 ${escapeText(row.before.covered_proxies)}/${escapeText(row.citation_proxy_count)}→${escapeText(row.after.covered_proxies)}/${escapeText(row.citation_proxy_count)}입니다.`;
 }).join(' ');
}
function show(id){
 const text=descriptions[id],item=evidence.topics[id];
 const sourceKeys={b1:'b1_software_proxy',b2:'b2_public_definition',b3:'b3_trace_dataset',d:'d_public_license_record',patent:'patent_actual_fields'};
 const access=evidence.data_access?.sources?.[sourceKeys[id]];
 const availability={
  b1:['공개 오류·수정·테스트 이력의 표본을 실제로 확보했습니다. 소프트웨어 사례이며 쇼핑몰 주문 이력은 아닙니다.','주문 실패 입력·사람의 보정 이유·처리 결과가 연결된 현업 기록은 아직 없습니다.'],
  b2:['공식 워크플로 JSON을 받아 노드·연결·설정 구조를 확인했습니다. 공개 예제에는 실행 이력이 없습니다.','회사 실행 이력은 권한 있는 인스턴스에서 받아야 합니다. 읽기·쓰기 의미와 업무 결과 정답도 필요합니다.'],
  b3:['공개 요구사항·코드·연결 정답 자료를 로컬에서 확인했습니다. 관계 탐색을 평가할 수 있습니다.','완료 판정에는 실제 변경 전후와 반드시 바뀌어야 하는 자료·검사 기준이 추가로 필요합니다.'],
  d:['공개 라이선스 문서와 공식 결정 설명을 확인했습니다. 공개 이유·범위·시점을 자료로 연결할 수 있습니다.','기업 내부 비공개 전제·과거 판단·재검토 정답은 아직 없습니다. 이 라이선스를 Python SDK에 적용하지 않습니다.'],
  patent:['기존 KIPRIS 성공 응답에서 실제 문헌 번호·제목·초록·공개일·분류 필드를 확인했습니다.','원문 근거와 사람의 포함·제외 판단이 필요합니다. API 이용 범위·호출 제한은 승인된 서비스별로 확인해야 합니다.']
 };
 const accessPanel=access?`<article class="panel"><h3>실제 업무 자료를 확보할 수 있는가?</h3><p>${escapeText(access.status==='acquired'?availability[id][0]:'이번 자료 접근 확인은 실패했습니다. 상세 기록을 확인하세요.')}</p><p>${escapeText(availability[id][1])}</p>${access.url?`<a href="${escapeText(access.url)}" target="_blank" rel="noopener">확인한 공개 자료 원문</a>`:''}<p>공개 자료 확보와 회사 현업 데이터 확보는 별도 조건입니다.</p></article>`:'';
 document.querySelectorAll('#tabs button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.topic===id)));
 const extra=id==='b3'?{public_trace:evidence.external_trace,public_changes:evidence.public_cases}:id==='patent'?{existing_baseline:evidence.patent_baseline,page_probe:evidence.patent_page_probe,expression_probe:evidence.patent_expression_probe}:id==='b2'?{public_cases:evidence.public_cases,n8n_probe:evidence.n8n_probe}:id==='b1'?{public_cases:evidence.public_cases}:{};
 const publicCases=evidence.public_cases?.cases;
 const publicSummary=publicCases&&['b1','b2','b3'].includes(id)?`<article class="panel"><h3>추가로 확보한 공개 사례</h3><p>재시도 오류 수정 PR: ${publicCases.retry_fix?.status==='failed'?'조회 실패':publicCases.retry_fix?.merged?'병합됨':'미병합'} · 변경 파일 ${publicCases.retry_fix?.files?.length??'미확인'}개. 공유 저장소 충돌 수정 PR: ${publicCases.shared_storage_conflict?.status==='failed'?'조회 실패':publicCases.shared_storage_conflict?.merged?'병합됨':'미병합'} · 변경 파일 ${publicCases.shared_storage_conflict?.files?.length??'미확인'}개.</p><p>이슈·수정 코드·테스트 변경의 공개 기록을 확보했습니다. 현업 주문별 해결 이력이나 완전한 변경 영향 정답은 아닙니다. U3에서 원본 시스템을 실행한 결과도 아닙니다.</p><a href="https://github.com/n8n-io/n8n/pull/8480" target="_blank" rel="noopener">재시도 수정 원문</a> · <a href="https://github.com/n8n-io/n8n/pull/25541" target="_blank" rel="noopener">공유 저장소 충돌 수정 제안</a></article>`:'';
 const source=id==='d'&&item.release_url?`<p><a href="${escapeText(item.release_url)}" target="_blank" rel="noopener">실제 릴리스</a> · <a href="${escapeText(item.comparison_url)}" target="_blank" rel="noopener">변경 원문</a></p>`:'';
 const diagnostic=id==='patent'&&evidence.patent_expression_probe?`<article class="panel"><h3>표현 차이 추가 조회</h3><p>오브젝트→객체·물체, 거리측정→거리 측정을 한 사례에서 시험했습니다. ${expressionSummary()}</p><p>이전에 확인한 사례의 작은 진단이며 일반 검색 성능이 아닙니다. 후보 증가를 검색 개선으로 해석하지 않습니다.</p></article>`:id==='b2'&&evidence.n8n_probe?`<article class="panel"><h3>실제 자동화 도구 실행</h3><p>${evidence.n8n_probe.status==='verified'?'실제 n8n에서 4개 순차 HTTP 워크플로를 실행했고 기대 저장 상태와 요청 순서를 확인했습니다.':'n8n 실행 검증이 완료되지 않았습니다. 이번 시도의 실패 정보는 상세 기록에 남겼습니다.'}</p><p>통제 입력이며 병렬 실행·실제 고객 시스템의 충돌 탐지 성능은 검증하지 않았습니다.</p></article>`:'';
 document.querySelector('#details').innerHTML=`<h2>${text.name}</h2><div class="evidence-grid"><article class="panel"><h3>입력과 실행</h3><p>${text.input}</p><p>${text.execution}</p></article><article class="panel"><h3>관찰 결과</h3><p>${item.status==='failed'?'이번 외부 조회는 실패했습니다. 아래 결과의 오류 유형을 확인하세요.':text.result}</p></article><article class="panel"><h3>사람이 결정할 것</h3><p>${text.human}</p></article><article class="panel"><h3>아직 확인하지 못한 것</h3><p>${text.unknown}</p></article></div>${source}${publicSummary}${diagnostic}${accessPanel}<details><summary>실행 기록과 측정값 펼치기</summary><pre>${escapeText(JSON.stringify({execution:item,data_access:access,...extra},null,2))}</pre></details>`;
}
fetch('execution-evidence.json').then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();}).then(data=>{
 evidence=data;document.querySelector('#run-time').textContent='실행 시각: '+new Date(data.run_at).toLocaleString('ko-KR');
 document.querySelector('#tabs').innerHTML=Object.entries(descriptions).map(([id,text])=>`<button class="secondary" data-topic="${id}" aria-pressed="false">${text.name}</button>`).join('');
 document.querySelector('#tabs').addEventListener('click',event=>{const button=event.target.closest('[data-topic]');if(button){history.replaceState(null,'','#'+button.dataset.topic);show(button.dataset.topic);}});const initial=location.hash.slice(1);show(descriptions[initial]?initial:'b1');
}).catch(()=>{document.querySelector('#run-time').textContent='실행 결과를 읽지 못했습니다. 페이지를 새로고침하거나 JSON 링크를 확인하세요.';});
