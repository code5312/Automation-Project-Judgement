const assert = require('node:assert/strict');
const {exceptionDecision, conflicts, changeState, ipSignal} = require('./engine');

assert.equal(exceptionDecision({type:'grade_sync_delay',consent:true},false).status,'approval');
assert.equal(exceptionDecision({type:'grade_sync_delay',consent:true},true).status,'ready');
assert.equal(exceptionDecision({type:'grade_sync_delay',consent:false},true).status,'manual');
assert.equal(exceptionDecision({type:'payment_mismatch',consent:true},true).status,'manual');
const prior=[{name:'마케팅',trigger:'new_inquiry',reads:['customer.status'],writes:{'customer.status':'관심 고객'},effect:'send_welcome'}];
const hits=conflicts(prior,{trigger:'new_inquiry',writes:{'customer.status':'처리 완료'},effect:'send_welcome'});
assert.deepEqual(new Set(hits.map(x=>x.kind)),new Set(['쓰기-쓰기','읽기-쓰기','중복 실행']));
assert.equal(conflicts(prior,{trigger:'consultation_end',writes:{'customer.memo':'추가'}}).length,0);
assert.equal(changeState('배송비 면제 기준은 삼만 원입니다.',['5만원','50000'],['3만원','30000']).state,'updated');
assert.equal(changeState('assert shipping_fee(50000) == 0',['5만원','50000'],['3만원','30000']).state,'stale');
assert.equal(changeState('고객님, 환불은 7일 안에 신청하세요.',['7일'],['14일']).state,'stale');
assert.equal(changeState('기간 안내 문구와 규칙을 대조한다.',['7일'],['14일']).state,'uncertain');
assert.equal(ipSignal({record:'trade_secret',text:'고객용 SDK에 내부 규칙 포함'}).premise,true);
assert.equal(ipSignal({record:'none',text:'새로운 센서 융합 알고리즘을 학회에 공개'}).state,'review');
console.log('회의용 판단 규칙 검증 통과');
