/* One-page product walkthrough for the 9/30 meeting. No network writes. */
const DATA = window.DEMO_DATA;
const ENGINE = window.DEMO_ENGINE;
const TOPICS = [
  ['overview','◈','전체 흐름'],['b1','01','반복 예외'],['b2','02','자동화 충돌'],
  ['b3','03','변경 완료'],['d','04','IP 사건'],['patent','05','특허 검색'],['summary','✓','회의 결론']
];
const state = {
  topic:'overview', b1Approved:false, b1Type:'grade_sync_delay', b1Consent:true, b1Result:null,
  b2Flow:'status', b2Findings:null, b2Action:null,
  b3Case:0, b3Choices:{}, b3Reasons:{}, b3Result:null,
  dCase:0, dChoices:{}, dReasons:{}, dResult:null,
  patentCase:0, patentChoices:{}, patentResult:null,
  vote:null, note:''
};
const $ = s => document.querySelector(s);
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function badge(text,kind){return '<span class="badge '+(kind||'')+'">'+escapeHtml(text)+'</span>'}
function stepper(steps){return '<div class="stepper">'+steps.map(x=>'<span>'+escapeHtml(x)+'</span>').join('')+'</div>'}
function hero(index,title,description,badges,steps){
  return '<div class="hero"><div>'+badges.join('')+'</div><h2>'+title+'</h2><p>'+description+'</p>'+stepper(steps)+'</div>';
}
function side(decision,evidence,question,source){
  return '<div class="stack"><div class="panel"><h3>사람이 결정하는 것</h3><p>'+decision+'</p></div>'+
    '<div class="panel"><h3>지금 확인된 것</h3><p>'+evidence+'</p></div>'+
    '<div class="panel"><h3>회의에서 확인할 질문</h3><p>'+question+'</p><p class="source">'+source+'</p></div></div>';
}
function shell(content,aside){return '<div class="content-grid"><div class="stack">'+content+'</div>'+aside+'</div>'}
function topicButton(id,label){return '<button class="secondary" data-topic="'+id+'">'+label+' →</button>'}
function field(label,id,options,value){
  return '<div class="field"><label for="'+id+'">'+label+'</label><select id="'+id+'">'+
    options.map(o=>'<option value="'+escapeHtml(o[0])+'" '+(String(value)===String(o[0])?'selected':'')+'>'+escapeHtml(o[1])+'</option>').join('')+'</select></div>';
}
function resultBox(title,body,kind){return '<div class="result '+(kind||'')+'"><h3>'+title+'</h3>'+body+'</div>'}
function renderNav(){
  $('#topic-nav').innerHTML=TOPICS.map(([id,icon,title])=>
    '<button class="nav-item '+(state.topic===id?'active':'')+'" data-topic="'+id+'" '+(state.topic===id?'aria-current="page"':'')+'><span>'+icon+'</span><span>'+title+'</span></button>').join('');
}
function render(){
  renderNav();
  const title=TOPICS.find(x=>x[0]===state.topic)[2];
  $('#page-title').textContent=title==='전체 흐름'?'사람판단 워크스페이스':title;
  const view={overview,b1,b2,b3,d,patent,summary}[state.topic]();
  $('#page-content').innerHTML=view;
}
function overview(){
  const cards=[
    ['b1','01','반복 예외','같은 문제가 다시 오면, 지난 사람의 해결을 자동 적용해도 될까요?','가상 업무'],
    ['b2','02','자동화 충돌','새 자동화가 기존 흐름의 상태나 행동을 망가뜨리지 않을까요?','가상 계약'],
    ['b3','03','변경 완료','정책을 바꾼 뒤 FAQ·설정·테스트까지 반영됐을까요?','기준선 실험'],
    ['d','04','IP 사건','공개 전에 검토해야 할 기술 변경을 놓치지 않았을까요?','가상 사건'],
    ['patent','05','특허 검색','검색 후보 중 사람이 먼저 원문을 확인할 문헌은 무엇일까요?','KIPRIS 탐색']
  ];
  const main='<div class="panel"><div class="panel-head"><div><h2>다섯 업무, 하나의 공통 구조</h2><p class="muted">사람의 결정을 없애지 않고, 결정 전의 탐색과 결정 후의 후속 작업을 보조합니다.</p></div></div>'+
    '<div class="metric-row"><div class="metric"><strong>5</strong><span>비교할 업무 후보</span></div><div class="metric"><strong>2</strong><span>기존 통제 실험 B-3·D</span></div><div class="metric"><strong>1</strong><span>실제 KIPRIS 탐색 축</span></div></div></div>'+
    cards.map(([id,n,title,desc,level])=>'<div class="panel"><div class="panel-head"><div>'+badge(n+' / '+level,id==='patent'?'green':'gray')+
      '<h3>'+title+'</h3><p class="muted">'+desc+'</p></div>'+topicButton(id,'체험하기')+'</div></div>').join('');
  const aside=side('시스템이 후보와 근거를 준비하고, 담당자가 승인·수정·보류를 선택합니다.',
    'B-3·D는 팀 제작 사례에서 기준선을 실행했습니다. 특허는 실제 공개 자료의 탐색 평가가 있고, B-1·B-2는 가상 업무 시연 단계입니다.',
    '어느 업무의 실제 입력·정답·사용자를 먼저 확보할 수 있을까요?','회의 목표: MVP 주제와 다음 검증 자료 선정');
  return hero('00','자동화의 끝에 사람의 판단을 남기다','각 후보를 눌러 사건 → 제안 → 사람 결정 → 후속 처리의 변화를 확인해 보세요.',
    [badge('9/30 회의 시연'),badge('입력 저장 없음')],['사건','후보와 근거','사람 결정','후속 처리'])+shell(main,aside);
}
function b1(){
  const history=[
    ['E-101','등급 정보 누락','CRM 등급 재조회 → 쿠폰 재발급','성공'],
    ['E-102','등급 동기화 지연','CRM 등급 재조회 → 쿠폰 재발급','성공'],
    ['E-103','수신 동의 철회','발급 중단 → 동의 상태 확인','정상 종료']
  ];
  const event={type:state.b1Type,consent:state.b1Consent};
  const suggestion=ENGINE.exceptionDecision(event,state.b1Approved);
  let main='<div class="panel"><div class="panel-head"><div><h3>1. 과거 해결 이력</h3><p class="muted small">같은 행동이 언제 성공했고, 언제 적용하면 안 되는지 비교합니다.</p></div>'+badge('예시 데이터','amber')+'</div>'+
    history.map(h=>'<div class="record"><div class="record-row"><h4>'+h[0]+' · '+h[1]+'</h4>'+badge(h[3],h[3]==='성공'?'green':'gray')+'</div><p>'+h[2]+'</p></div>').join('')+'</div>'+
    '<div class="panel"><h3>2. 다음 사건을 입력해 보기</h3><div class="controls">'+
    field('예외 유형','b1-type',[['grade_sync_delay','등급 동기화 지연'],['grade_missing','등급 정보 누락'],['payment_mismatch','결제 금액 불일치']],state.b1Type)+
    field('고객 수신 동의','b1-consent',[['yes','유효'],['no','철회됨']],state.b1Consent?'yes':'no')+'</div>'+
    resultBox('시스템 제안: '+suggestion.action,'<p>'+suggestion.reason+'</p>',suggestion.status==='manual'?'warn':'')+
    '<div class="controls"><button class="primary" data-action="b1-evaluate">이 사건 처리 경로 확인</button>'+
    '<button class="secondary" data-action="b1-approve">'+(state.b1Approved?'승인 취소':'제안 규칙 승인')+'</button></div>'+
    (state.b1Result?resultBox('3. 후속 처리',state.b1Result,state.b1Approved?'success':'warn'):'')+'</div>';
  return hero('01','반복되는 예외를 규칙으로 바꿀 수 있을까?','과거의 성공 행동을 그대로 복사하기 전에 적용 조건과 금지 조건을 확인합니다.',
    [badge('B-1'),badge('가상 업무','amber')],['예외 발생','유사 해결 확인','규칙 승인','다음 사건 처리'])+
    shell(main,side('운영자가 해결 규칙의 적용 범위와 자동 적용 여부를 승인합니다.','동의 철회 사건은 재발급 규칙에서 제외됩니다. 실제 예외·결과 이력은 아직 없습니다.','한 업무에서 예외·사람 행동·성공 결과를 함께 구할 수 있을까요?','검증 단계: 개념·가상 규칙'));
}
const EXISTING=[
  {name:'마케팅 관심 고객 지정',trigger:'new_inquiry',reads:['customer.status'],writes:{'customer.status':'관심 고객'}},
  {name:'기존 환영 메일',trigger:'new_inquiry',reads:['customer.email'],writes:{},effect:'send_welcome'}
];
const NEW_FLOWS={
  status:{name:'CS 처리 완료',trigger:'new_inquiry',reads:['customer.status'],writes:{'customer.status':'처리 완료'}},
  mail:{name:'새 환영 메일',trigger:'new_inquiry',reads:['customer.email'],writes:{},effect:'send_welcome'},
  audit:{name:'상태 변경 감사',trigger:'new_inquiry',reads:['customer.status'],writes:{'audit.last_status':'기록'}},
  memo:{name:'상담 메모',trigger:'consultation_end',reads:['customer.id'],writes:{'customer.memo':'상담 기록'}}
};
function b2(){
  const flow=NEW_FLOWS[state.b2Flow];
  const findings=state.b2Findings;
  let main='<div class="panel"><h3>1. 이미 운영 중인 자동화</h3>'+
    EXISTING.map(x=>'<div class="record"><h4>'+x.name+'</h4><p class="small">시작 사건: 신규 문의 · 읽기: '+escapeHtml(x.reads.join(', '))+' · 쓰기/행동: '+escapeHtml(Object.keys(x.writes).join(', ')||x.effect)+'</p></div>').join('')+'</div>'+
    '<div class="panel"><h3>2. 배포할 자동화 선택</h3><div class="controls">'+field('새 흐름','b2-flow',Object.entries(NEW_FLOWS).map(([id,x])=>[id,x.name]),state.b2Flow)+
    '<button class="primary" data-action="b2-scan">배포 전 검사</button></div><div class="record"><h4>'+flow.name+'</h4><p>사건: '+flow.trigger+' · 읽기: '+flow.reads.join(', ')+' · 쓰기/행동: '+(Object.keys(flow.writes).join(', ')||flow.effect)+'</p></div>'+
    (findings!==null?'<div class="result '+(findings.length?'warn':'success')+'"><h3>3. 검사 결과 · '+findings.length+'건</h3>'+
      (findings.length?'<ul class="item-list">'+findings.map(f=>'<li><strong>'+f.kind+'</strong> · '+f.with+' — '+escapeHtml(f.detail)+'</li>').join('')+'</ul>':'<p>현재 입력 계약에서는 직접 충돌 후보가 없습니다. 실제 실행 결과는 별도 시험이 필요합니다.</p>')+
      '<div class="controls"><button class="secondary" data-action="b2-fix">수정·격리 시험 요청</button><button class="secondary" data-action="b2-hold">배포 보류</button></div></div>':'')+
    (state.b2Action?resultBox('4. 사람 결정 후',state.b2Action,'success'):'')+'</div>';
  return hero('02','새 자동화가 기존 흐름을 깨뜨리지 않을까?','같은 사건의 읽기·쓰기 범위와 중복 행동을 비교해 충돌 후보를 보여줍니다.',
    [badge('B-2'),badge('가상 n8n 계약','amber')],['새 흐름 등록','계약 비교','사람 검토','격리 시험'])+
    shell(main,side('운영자가 충돌의 실제 영향과 수정·배포 여부를 결정합니다.','쓰기-쓰기, 읽기-쓰기, 중복 실행을 제한된 계약 자료로 계산합니다. 실제 n8n 정의와 실행은 연결하지 않았습니다.','자동화별 읽기·쓰기 계약이나 실행 기록을 확보할 수 있을까요?','검증 단계: 결정론적 충돌 계산 시연'));
}
function b3(){
  const c=DATA.cases[state.b3Case];
  let main='<div class="panel"><div class="panel-head"><div><h3>1. 변경 요청</h3><p class="muted">'+escapeHtml(c.change)+'</p></div>'+badge('팀 제작 사례','amber')+'</div>'+
    field('사례 선택','b3-case',DATA.cases.map((x,i)=>[i,x.name]),state.b3Case)+'</div>'+
    '<div class="panel"><div class="panel-head"><div><h3>2. 영향 자료 확정</h3><p class="muted small">파란 테두리는 기존 BM25가 올린 후보입니다. 사람이 관련성을 결정하면 수정 후 값을 확인합니다.</p></div>'+badge(c.artifacts.length+'개 자료')+'</div>'+
    c.artifacts.map((x,i)=>{
      const key=state.b3Case+':'+x.id,choice=state.b3Choices[key]||'pending';
      const check=ENGINE.changeState(x.after,c.old_forms,c.new_forms);
      return '<div class="record '+(x.suggested?'suggested':'')+'"><div class="record-row"><div><h4>'+escapeHtml(x.id)+' · '+escapeHtml(x.kind)+'</h4>'+
        (x.suggested?badge('검색 후보'):'')+'</div>'+badge(check.state==='stale'?'이전 값 잔존 후보':check.state==='updated'?'새 값 확인 후보':'문맥 확인',check.state==='stale'?'amber':'gray')+'</div>'+
        '<p>'+escapeHtml(x.before)+'</p><details><summary>변경 후 자료와 검증 근거 보기</summary><p>'+escapeHtml(x.after)+'</p><span class="small muted">'+check.reason+' 값 일치에 한정한 검사입니다.</span></details>'+
        '<div class="controls">'+field('사람의 영향 판단','b3-'+i,[['pending','아직 판단 안 함'],['related','관련 있음'],['unrelated','관련 없음'],['hold','추가 확인']],choice)+'</div>'+ 
        '<div class="field"><label for="b3-reason-'+i+'">판단 이유·수정 범위 (선택)</label><textarea id="b3-reason-'+i+'" placeholder="예: 관련은 있으나 직접 수정할 자료는 아님">'+escapeHtml(state.b3Reasons[key]||'')+'</textarea></div></div>';
    }).join('')+'<button class="primary" data-action="b3-check">3. 완료 여부 계산</button>'+
    (state.b3Result?resultBox(state.b3Result.title,state.b3Result.body,state.b3Result.kind):'')+'</div>';
  return hero('03','변경 지시가 모든 자료에 반영됐을까?','표현이 다른 자료를 찾고, 사람이 영향 범위를 확정한 뒤 값이 남아 있는 자료를 다시 봅니다.',
    [badge('B-3'),badge('팀 제작 통제 사례','amber')],['정책 변경','영향 후보','사람 확정','완료 재검증'])+
    shell(main,side('운영자가 영향 범위를 정하고, 수정 담당자가 반영한 뒤 완료를 확정합니다.','검색은 기존 BM25, 값 검사는 이 사례의 숫자·기간 표현만 정규화합니다. 임의의 정책을 이해하는 검사는 아닙니다.','관련 자료와 직접 수정해야 하는 자료를 어떻게 구분할까요?','검증 단계: 통제 사례 2개 + 외부 요구사항→코드 검색 부분 검증'));
}
function d(){
  const c=DATA.cases[state.dCase];
  let main='<div class="panel"><h3>1. 예정된 외부 공개</h3><p>'+escapeHtml(c.release)+'</p>'+
    field('사례 선택','d-case',DATA.cases.map((x,i)=>[i,x.release]),state.dCase)+'</div>'+
    '<div class="panel"><div class="panel-head"><div><h3>2. 사건별 검토</h3><p class="muted small">시스템이 놓칠 수 있으므로 사람은 검토 요청·보류·제외를 직접 선택합니다.</p></div>'+badge(c.events.length+'개 사건')+'</div>'+
    c.events.map((x,i)=>{
      const signal=ENGINE.ipSignal(x),key=state.dCase+':'+x.id,choice=state.dChoices[key]||'pending';
      return '<div class="record '+(signal.state==='review'?'suggested':'')+'"><div class="record-row"><h4>'+escapeHtml(x.id)+'</h4>'+
        badge(signal.state==='review'?'검토 신호':signal.state==='hold'?'정보 확인 신호':'신호 낮음',signal.state==='review'?'amber':'gray')+'</div>'+
        '<p>'+escapeHtml(x.text)+'</p><p class="small muted">기존 기록: '+escapeHtml(x.record)+(x.premise?' · 판단 전제: '+escapeHtml(x.premise):'')+'</p>'+
        '<details><summary>시스템 근거 보기</summary><p>'+escapeHtml(signal.reason)+'</p></details>'+
        field('사람 판단','d-'+i,[['pending','아직 판단 안 함'],['review','IP 검토 요청'],['hold','정보 부족 · 보류'],['skip','추가 검토 불필요']],choice)+
        '<div class="field"><label for="d-reason-'+i+'">판단 이유·필요한 정보 (선택)</label><textarea id="d-reason-'+i+'" placeholder="예: 공개 범위 확인 후 다시 판단">'+escapeHtml(state.dReasons[key]||'')+'</textarea></div></div>';
    }).join('')+'<button class="primary" data-action="d-check">3. 판단 카드 만들기</button>'+
    (state.dResult?resultBox(state.dResult.title,state.dResult.body,state.dResult.kind):'')+'</div>';
  return hero('04','검토를 시작해야 하는 사건을 놓치지 않을까?','외부 공개 전에 새 기술과 과거 비공개 판단의 전제 변화를 찾아 사람에게 질문합니다.',
    [badge('D'),badge('팀 제작 가상 사건','amber')],['공개 사건','검토 신호','담당자 결정','전제 재확인'])+
    shell(main,side('IP 담당자가 검토 요청·정보 부족·제외를 결정하고 판단 이유를 남깁니다.','현재는 표현 규칙과 가상 기록에 의존합니다. 특허성이나 공개 가능 여부를 자동 결정하지 않습니다.','실제 검토 누락 사건과 과거 IP 판단의 이유·전제를 확보할 수 있을까요?','검증 단계: 통제 사례 2개 + 사용자 1명 검토'));
}
function patent(){
  const c=DATA.patent[state.patentCase],f=DATA.patent_funnel;
  let main='<div class="panel"><h3>1. 공개 특허 검색 파이프라인</h3><p class="muted">이 채팅에서 KIPRIS로 수집해 평가한 탐색 결과입니다. 이 페이지는 API를 새로 호출하지 않습니다.</p>'+
    '<div class="metric-row"><div class="metric"><strong>'+f.queries+'</strong><span>검토한 질의</span></div><div class="metric"><strong>'+f.citation_proxy_pairs+'</strong><span>인용 proxy 연결</span></div><div class="metric"><strong>'+f.retrieved_pairs+'</strong><span>실제 검색 후보에 포함</span></div></div>'+
    '<div class="funnel"><span style="width:'+Math.round(f.retrieved_pairs/f.citation_proxy_pairs*100)+'%"></span></div>'+
    '<p class="small muted">검색어 최대 2개·검색어별 첫 500행 조건에서 15/77만 후보에 포함됐습니다. 정답 문헌을 후보에 강제로 넣지 않은 결과입니다.</p></div>'+
    '<div class="panel"><h3>2. 저장된 검색 사례 살펴보기</h3>'+
    field('검토 기술','patent-case',DATA.patent.map((x,i)=>[i,x.query]),state.patentCase)+
    '<div class="result"><h3>'+escapeHtml(c.query)+'</h3><p>출원번호 '+escapeHtml(c.application)+'</p><p class="small">'+escapeHtml(c.note)+'</p></div>'+
    c.ranked.map((id,i)=>{
      const key=state.patentCase+':'+id,choice=state.patentChoices[key]||'pending';
      return '<div class="record"><div class="record-row"><h4>저장 순위 '+(state.patentCase===0?i+1:54)+'위 · '+escapeHtml(id)+'</h4>'+badge('공개 공보 식별자','gray')+'</div>'+
        '<p class="small muted">이 정적 시연에는 공보의 초록·청구항이 없어 관련성 판단을 완료할 수 없습니다.</p>'+
        field('사람의 다음 행동','patent-'+i,[['pending','아직 확인 안 함'],['fetch','원문 확인 요청'],['hold','보류']],choice)+'</div>';
    }).join('')+'<button class="primary" data-action="patent-check">3. 검토 작업 만들기</button>'+
    (state.patentResult?resultBox(state.patentResult.title,state.patentResult.body,'warn'):'')+'</div>';
  return hero('05','검색된 특허 중 무엇을 먼저 검토할까?','진주님 작업의 검색 후 사람 검토 흐름과 이 채팅의 검색 평가가 만나는 지점입니다. D의 사건 탐지와는 별도 질문입니다.',
    [badge('특허 검색 보조'),badge('KIPRIS 공개 자료','green')],['기술 입력','후보 수집·순위','원문 검토','사람 판단'])+
    shell(main,side('담당자가 문헌 원문과 근거를 보고 검토 우선순위·판단 이유를 결정합니다.','정답 주입 순위 평가와 실제 후보 수집 결과는 구분해야 합니다. 이 화면의 번호만으로 문헌 관련성을 판단할 수 없습니다.','후보 포함률을 올릴 검색어·IPC 전략과 원문 확인 자료를 마련할 수 있을까요?','검증 단계: 실제 KIPRIS 탐색 30건, 인용 proxy 기반'));
}
function summary(){
  const options=[['b1','반복 예외'],['b2','자동화 충돌'],['b3','변경 완료'],['d','IP 사건 탐지'],['patent','특허 검색 보조']];
  let main='<div class="panel"><h2>회의에서 한 가지를 정한다면?</h2><p class="muted">사용자·반복 업무·확보할 수 있는 데이터·사람의 결정 지점을 기준으로 다음 검증 후보를 고르세요.</p>'+
    '<div class="feedback-grid">'+options.map(([id,title])=>'<button class="'+(state.vote===id?'active':'')+'" data-vote="'+id+'">'+title+'</button>').join('')+'</div>'+
    '<div class="field" style="margin-top:18px"><label for="meeting-note">선택 이유와 다음에 구할 자료</label><textarea id="meeting-note" placeholder="예: 변경 전후 FAQ와 설정 자료를 받을 수 있음">'+escapeHtml(state.note)+'</textarea></div>'+
    '<div class="controls"><button class="primary" data-action="download">내 회의 의견 JSON 내려받기</button></div>'+
    '<p class="small muted">서버에 자동 제출되지 않습니다. 받은 파일을 회의 진행자에게 직접 전달해야 합니다.</p></div>';
  const aside=side('팀이 우선 검증할 한 업무와 필요한 실제 자료를 결정합니다.','B-3은 가장 구체적인 변경 완료 흐름, D·특허는 서로 다른 IP 업무, B-1·B-2는 실제 이력·계약 확보가 관문입니다.','다음 회의까지 누가 어떤 자료를 확보할 수 있을까요?','회의 기록은 개인 다운로드 파일에만 남습니다.');
  return hero('✓','회의 결론을 남겨 주세요','화면의 완성도와 실제 업무 검증 수준을 구분해, 다음에 검증할 후보를 정합니다.',
    [badge('한 명당 한 의견'),badge('서버 저장 없음','amber')],['후보 체험','근거 비교','우선순위 선택','자료 확보'])+shell(main,aside);
}
function changeTopic(id){state.topic=id;render();$('#page-content').focus()}
document.addEventListener('click',event=>{
  const topic=event.target.closest('[data-topic]');
  if(topic){changeTopic(topic.dataset.topic);return}
  const vote=event.target.closest('[data-vote]');
  if(vote){state.vote=vote.dataset.vote;render();return}
  const action=event.target.closest('[data-action]');
  if(!action)return;
  switch(action.dataset.action){
    case 'b1-approve': state.b1Approved=!state.b1Approved;state.b1Result=null;break;
    case 'b1-evaluate':{
      const answer=ENGINE.exceptionDecision({type:state.b1Type,consent:state.b1Consent},state.b1Approved);
      state.b1Result='<p><strong>'+answer.action+'</strong></p><p>'+answer.reason+'</p>';break;
    }
    case 'b2-scan':state.b2Findings=ENGINE.conflicts(EXISTING,NEW_FLOWS[state.b2Flow]);state.b2Action=null;break;
    case 'b2-fix':state.b2Action='<p>조건·쓰기 대상을 조정한 뒤 격리 시험을 요청합니다. 이 회의 시연은 실제 n8n을 실행하지 않습니다.</p>';break;
    case 'b2-hold':state.b2Action='<p>배포를 보류하고 운영자에게 충돌 근거와 미확인 사항을 전달합니다.</p>';break;
    case 'b3-check':{
      const c=DATA.cases[state.b3Case],counts={pending:0,unrelated:0,hold:0,updated:0,stale:0,mixed:0,uncertain:0},work=[];
      for(const x of c.artifacts){
        const choice=state.b3Choices[state.b3Case+':'+x.id]||'pending';
        if(choice==='related'){const check=ENGINE.changeState(x.after,c.old_forms,c.new_forms);counts[check.state]++;if(check.state!=='updated')work.push(x.id+' ('+check.reason+')')}
        else counts[choice]++;
      }
      const blocked=counts.stale+counts.mixed+counts.uncertain+counts.hold+counts.pending;
      state.b3Result={title:blocked?'변경 완료 보류':'사람 판단 범위에서 완료 후보',kind:blocked?'warn':'success',
        body:'<p>새 값 확인 '+counts.updated+' · 이전 값 잔존 '+counts.stale+' · 문맥 확인 '+(counts.mixed+counts.uncertain)+' · 관련 없음 '+counts.unrelated+' · 보류/미판단 '+(counts.hold+counts.pending)+'</p>'+
          (work.length?'<p>재확인 작업: '+escapeHtml(work.join(', '))+'</p>':'')+'<p class="small">값 일치와 사람의 영향 판단을 조합한 결과입니다. 실제 시스템 반영 완료를 증명하지 않습니다.</p>'};
      break;
    }
    case 'd-check':{
      const c=DATA.cases[state.dCase],r=[],h=[],premise=[],pending=[];
      for(const x of c.events){
        const choice=state.dChoices[state.dCase+':'+x.id]||'pending';
        if(choice==='review'){r.push(x.id);if(ENGINE.ipSignal(x).premise)premise.push(x.id)}
        if(choice==='hold')h.push(x.id);
        if(choice==='pending')pending.push(x.id);
      }
      state.dResult={title:'검토 요청 '+r.length+'건 · 추가 정보 '+h.length+'건',kind:h.length||pending.length?'warn':'',
        body:'<p>담당자 검토 카드: '+escapeHtml(r.join(', ')||'없음')+'</p><p>정보 요청: '+escapeHtml(h.join(', ')||'없음')+
          '</p><p>과거 판단 전제 재확인: '+escapeHtml(premise.join(', ')||'없음')+'</p><p class="small">미판단 '+pending.length+'건. 이는 업무 요청 목록이며 특허성·공개 가능 여부의 결론이 아닙니다.</p>'};
      break;
    }
    case 'patent-check':{
      const c=DATA.patent[state.patentCase],fetch=[],hold=[];
      for(const id of c.ranked){const choice=state.patentChoices[state.patentCase+':'+id]||'pending';if(choice==='fetch')fetch.push(id);if(choice==='hold')hold.push(id)}
      state.patentResult={title:'원문 확인 작업 '+fetch.length+'건',
        body:'<p>원문 요청: '+escapeHtml(fetch.join(', ')||'없음')+'</p><p>보류: '+escapeHtml(hold.join(', ')||'없음')+
          '</p><p class="small">원문 초록·청구항 확인 후에만 기술 관련성을 검토할 수 있습니다.</p>'};
      break;
    }
    case 'download':{
      state.note=$('#meeting-note').value;
      const payload={schema:'u3-meeting-feedback-v1',created_at:new Date().toISOString(),vote:state.vote,note:state.note,
        b1:{approved:state.b1Approved,type:state.b1Type,consent:state.b1Consent},
        b2:{flow:state.b2Flow,findings:state.b2Findings,action:state.b2Action},
        b3:{case:state.b3Case,choices:state.b3Choices,reasons:state.b3Reasons},
        d:{case:state.dCase,choices:state.dChoices,reasons:state.dReasons},
        patent:{case:state.patentCase,choices:state.patentChoices}};
      const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
      const anchor=document.createElement('a');anchor.href=url;anchor.download='u3-meeting-feedback.json';anchor.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);return;
    }
  }
  render();
});
document.addEventListener('change',event=>{
  const id=event.target.id,value=event.target.value;
  if(id==='b1-type'){state.b1Type=value;state.b1Result=null}
  else if(id==='b1-consent'){state.b1Consent=value==='yes';state.b1Result=null}
  else if(id==='b2-flow'){state.b2Flow=value;state.b2Findings=null;state.b2Action=null}
  else if(id==='b3-case'){state.b3Case=Number(value);state.b3Result=null}
  else if(id.startsWith('b3-')){state.b3Choices[state.b3Case+':'+DATA.cases[state.b3Case].artifacts[Number(id.slice(3))].id]=value;state.b3Result=null}
  else if(id==='d-case'){state.dCase=Number(value);state.dResult=null}
  else if(id.startsWith('d-')){state.dChoices[state.dCase+':'+DATA.cases[state.dCase].events[Number(id.slice(2))].id]=value;state.dResult=null}
  else if(id==='patent-case'){state.patentCase=Number(value);state.patentResult=null}
  else if(id.startsWith('patent-')){state.patentChoices[state.patentCase+':'+DATA.patent[state.patentCase].ranked[Number(id.slice(7))]]=value;state.patentResult=null}
  else return;
  render();
});
document.addEventListener('input',event=>{
  const id=event.target.id;
  if(id==='meeting-note')state.note=event.target.value;
  else if(id.startsWith('b3-reason-')){
    const item=DATA.cases[state.b3Case].artifacts[Number(id.slice(10))];
    if(item)state.b3Reasons[state.b3Case+':'+item.id]=event.target.value;
  }else if(id.startsWith('d-reason-')){
    const item=DATA.cases[state.dCase].events[Number(id.slice(9))];
    if(item)state.dReasons[state.dCase+':'+item.id]=event.target.value;
  }
});
$('#summary-button').onclick=()=>changeTopic('summary');
render();
