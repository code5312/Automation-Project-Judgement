const descriptions={
 b1:{name:'B-1 반복 예외',input:'통제된 주문 입력과 사람이 지정한 상품 매핑. 실제 고객 주문은 아닙니다.',execution:'로컬 HTTP 서버 → 상품 검증 → SQLite 저장 → 동일 주문 재시도.',result:'매핑 누락은 HTTP 422, 보정 후 200. 같은 주문 재시도는 DB 1건 유지, 다른 SKU 재시도는 409로 차단.',human:'재사용 규칙의 범위를 채널·상품코드·용량으로 제한합니다. 다른 용량과 채널은 보류합니다.',unknown:'실제 업무의 해결 이력에서 규칙을 발견하거나 현업 정확도를 측정한 것은 아닙니다.'},
 b2:{name:'B-2 자동화 충돌',input:'마케팅과 CS가 같은 고객 상태를 수정하는 통제된 두 자동화 클라이언트.',execution:'각 흐름이 실제 HTTP 업데이트를 보내고 SQLite 최종 상태를 읽었습니다.',result:'실행 순서 2가지의 최종 상태가 달랐습니다. 목적별 상태 필드를 분리하자 두 순서의 결과가 같았습니다.',human:'업무상 상태를 분리해도 되는지 결정합니다. 필드 분리가 모든 충돌의 해결책은 아닙니다.',unknown:'실제 n8n 실행·동시성·회사 자동화 정의는 아직 확인하지 않았습니다.'},
 b3:{name:'B-3 변경 완료',input:'격리된 작은 배송 프로젝트의 실제 Python 코드·정책·FAQ·상담 파일.',execution:'파일을 실제 수정한 뒤 배송 함수를 실행하고 문서 잔존 값을 검사했습니다.',result:'코드·정책·FAQ만 변경하면 상담 문구가 남아 완료를 보류합니다. 보정 후 29,999·30,000·50,000원 검사와 문서 검사가 통과합니다.',human:'실제 프로젝트의 영향 범위와 완료 조건을 확인합니다.',unknown:'영향 파일 목록을 사전에 지정했습니다. 자동 영향 탐색의 검증은 별도 공개 데이터 검색 실험 수준입니다.'},
 d:{name:'D IP 사건 탐지',input:'GitHub의 Sentry Python SDK 공개 릴리스 2개와 변경 파일 메타데이터.',execution:'GitHub API에서 릴리스와 두 버전의 비교 결과를 조회했습니다.',result:'실제 공개 시점·버전·변경 파일을 가져오는 것은 가능했습니다. 이 변화가 IP 검토 대상인지 판단하는 것은 아직 미검증입니다.',human:'비공개 전제와 과거 판단 기록을 연결하고 재검토 필요성을 결정해야 합니다.',unknown:'공개 저장소에는 해당 회사의 IP 판단 기록이 없습니다. 모든 SDK 변경을 IP 사건으로 분류하지 않습니다.'},
 patent:{name:'특허 검색 보조',input:'기존 KIPRIS 키와 실제 공개 문헌, 기존 30개 질의의 인용 문헌 대용 평가자료.',execution:'KIPRIS 문헌 1건을 재조회하고 기존 캐시의 검색 평가를 재실행했습니다. 추가 페이지 검색은 별도 작은 진단입니다.',result:'문헌 조회는 성공했습니다. 기존 후보 확보는 77쌍 중 15쌍이며, 부족한 후보를 순위 조정만으로 회수할 수 없습니다.',human:'원문 근거와 기술 관계를 검토합니다. 인용 이력은 법적 정답이 아닙니다.',unknown:'새 검색 전략의 일반 성능·신규성·침해 여부를 검증하지 않았습니다.'}
};
const escapeText=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let evidence;
function show(id){
 const text=descriptions[id],item=evidence.topics[id];
 document.querySelectorAll('#tabs button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.topic===id)));
 const extra=id==='b3'?{public_trace:evidence.external_trace}:id==='patent'?{existing_baseline:evidence.patent_baseline,page_probe:evidence.patent_page_probe}:{};
 const source=id==='d'&&item.release_url?`<p><a href="${escapeText(item.release_url)}" target="_blank" rel="noopener">실제 릴리스</a> · <a href="${escapeText(item.comparison_url)}" target="_blank" rel="noopener">변경 원문</a></p>`:'';
 document.querySelector('#details').innerHTML=`<h2>${text.name}</h2><div class="evidence-grid"><article class="panel"><h3>입력과 실행</h3><p>${text.input}</p><p>${text.execution}</p></article><article class="panel"><h3>관찰 결과</h3><p>${item.status==='failed'?'이번 외부 조회는 실패했습니다. 아래 결과의 오류 유형을 확인하세요.':text.result}</p></article><article class="panel"><h3>사람이 결정할 것</h3><p>${text.human}</p></article><article class="panel"><h3>아직 확인하지 못한 것</h3><p>${text.unknown}</p></article></div>${source}<details><summary>실행 기록과 측정값 펼치기</summary><pre>${escapeText(JSON.stringify({execution:item,...extra},null,2))}</pre></details>`;
}
fetch('execution-evidence.json').then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();}).then(data=>{
 evidence=data;document.querySelector('#run-time').textContent='실행 시각: '+new Date(data.run_at).toLocaleString('ko-KR');
 document.querySelector('#tabs').innerHTML=Object.entries(descriptions).map(([id,text])=>`<button class="secondary" data-topic="${id}" aria-pressed="false">${text.name}</button>`).join('');
 document.querySelector('#tabs').addEventListener('click',event=>{const button=event.target.closest('[data-topic]');if(button)show(button.dataset.topic);});show('b1');
}).catch(()=>{document.querySelector('#run-time').textContent='실행 결과를 읽지 못했습니다. 페이지를 새로고침하거나 JSON 링크를 확인하세요.';});
