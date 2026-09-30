const assert=require('node:assert/strict'),fs=require('node:fs'),E=require('./service-engine');
const data=JSON.parse(fs.readFileSync(__dirname+'/service-data.json','utf8'));
const [a,b]=data.flows;
assert.equal(E.compare(a,b).conflicts.length,1);
assert.notDeepEqual(E.outcomes(a,b).ab,E.outcomes(a,b).ba);
const fixed=JSON.parse(JSON.stringify(b));fixed.nodes[0].parameters.jsonBody='{"cs_status":"support_pending"}';
assert.equal(E.compare(a,fixed).conflicts.length,0);
assert.deepEqual(E.outcomes(a,fixed).ab,E.outcomes(a,fixed).ba);
assert.throws(()=>E.outcomes(data.publicWorkflow,b),/보류/);
const disabled=JSON.parse(JSON.stringify(a));disabled.nodes[0].disabled=true;assert.equal(E.workflow(disabled).writes.length,0);
const noBody=JSON.parse(JSON.stringify(a));noBody.nodes[0].parameters.sendBody=false;assert.equal(E.workflow(noBody).writes.length,0);assert.equal(E.workflow(noBody).unknown.length,1);
const dynamic=JSON.parse(JSON.stringify(a));dynamic.nodes[0].parameters.url='={{ $json.url }}';assert.equal(E.workflow(dynamic).unknown.length,1);
const project=JSON.parse(JSON.stringify(data.project));
const partial=E.updateProject(project,['policy.md','shipping.json']);assert(E.checkProject(partial).findings.some(f=>f.path==='cs.md'));
const complete=E.updateProject(project,project.artifacts.map(f=>f.path));const tests=complete.artifacts.find(f=>f.scope==='tests');tests.content=JSON.stringify([{amount:50000,expectedFee:0},{amount:29999,expectedFee:3000},{amount:30000,expectedFee:0}]);
assert.equal(E.checkProject(complete).complete,true);assert.equal(complete.artifacts.find(f=>f.path==='payment.json').content,'{"maxPayment":50000}');assert.equal(E.checkProject(complete).results[0].pass,true);
const amounts={artifacts:['150000원','500000원','15만원','십오만원','50000원','5만원','오만 원'].map((content,i)=>({path:String(i),scope:'general',content}))};assert.equal(E.updateProject(amounts,amounts.artifacts.map(f=>f.path)).artifacts.map(f=>f.content).join(' '),'150000원 500000원 15만원 십오만원 30000원 3만원 삼만 원');
assert.equal(E.watch([{id:'one',prefixes:['sentry_sdk/integrations/'],premise:'old release'}],data.sdk)[0].needsReview,true);
assert.equal(E.watch([{id:'none',prefixes:['not-in-sdk/'],premise:'old release'}],data.sdk)[0].needsReview,false);
assert.throws(()=>E.watch([{id:'one',prefixes:[''],premise:'old'}],data.sdk));
assert(E.search(data.patents,'거리측정 객체').length>0);assert.deepEqual(E.search(data.patents,'오브젝트').map(r=>r.id),E.search(data.patents,'객체').map(r=>r.id));assert.equal(E.search(data.incidents,'ascii.qdp read serr')[0].id,'astropy__astropy-14365');
console.log('실제 입력의 쓰기 충돌·보류·문서 누락·경계값·변경 연결·문헌 검색 검사 통과');

const commaAmounts={artifacts:[{path:'p',scope:'general',content:'50,000,000원 150,000원 / 50,000원'}]};assert.equal(E.updateProject(commaAmounts,['p']).artifacts[0].content,'50,000,000원 150,000원 / 30000원');

assert.throws(()=>E.updateProject({artifacts:[{path:'mixed',scope:'general',content:'무료배송 기준 5만원 / 적립금 사용 한도 5만원'}]},['mixed']),/보류/);
