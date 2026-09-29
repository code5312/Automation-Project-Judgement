"""Build a static, label-blind review page for teammate feedback.

The page never sends data to a server. Reviewers download their decisions as JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from run_validation import HERE, change_probe, ip_probe


def public_case(filename: str) -> dict:
    source = HERE / filename
    fixture = json.loads(source.read_text(encoding="utf-8"))
    change = fixture["change_completion"]
    ip = fixture["ip_review"]
    ranked = set(change_probe(change)["ranked_ids"])
    ip_predictions = {row["id"]: row["review_candidate"]
                      for row in ip_probe(ip)["review_candidates"]}
    return {
        "id": filename,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "change": change["change"],
        "artifacts": [
            {"id": row["id"], "kind": row["kind"], "before": row["before"],
             "after": row["after"], "suggested": row["id"] in ranked}
            for row in change["artifacts"]
        ],
        "release": ip["release_event"],
        "events": [
            {"id": row["id"], "text": row["text"],
             "record": row["review_record"], "premise": row["prior_premise"],
             "suggested": ip_predictions[row["id"]]}
            for row in ip["events"]
        ],
    }


PAGE = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>사람판단 주제 검토 실험</title>
<style>
:root{font-family:system-ui,"Malgun Gothic",sans-serif;color:#16202d;background:#f4f6fa}body{margin:0 auto;max-width:1100px;padding:24px}
h1{margin:0 0 8px}p{line-height:1.55}.note{background:#fff4d8;border-left:4px solid #b77700;padding:12px 16px;margin:16px 0}
.controls{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}select,input,button,textarea{font:inherit;padding:8px;border:1px solid #b7c2d1;border-radius:6px}
button{background:#173f77;color:white;cursor:pointer;border:0}.card{background:white;border:1px solid #dce2e9;border-radius:10px;padding:16px;margin:12px 0}
.candidate{border-left:5px solid #326dba}.meta{font-size:.9rem;color:#50627a}.text{white-space:pre-wrap;margin:8px 0}
.choices{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0}.choices label{white-space:nowrap}.reason{width:98%;min-height:42px}
.after{background:#f6f8fb;padding:8px;border-radius:5px}h2{margin-top:32px}
</style></head><body>
<h1>사람판단 주제 검토 실험</h1>
<p>같은 저장소에서 B-3 변경 완료 검증과 D IP 검토 요청 후보를 살펴보는 작은 실험 화면입니다.</p>
<div class="note"><strong>팀 제작 가상 사례입니다.</strong> 시스템의 추천은 정답이 아닙니다. IP 항목은 법률 판단이 아니라 추가 검토가 필요한지 표시해 주세요. 입력 내용은 서버로 전송되지 않으며, 마지막에 JSON 파일을 내려받아 직접 공유해야 합니다.</div>
<div class="controls"><label>사례 <select id="case"></select></label><label>검토자 별칭 <input id="reviewer" placeholder="예: reviewer-1"></label><button id="download">판단 기록 내려받기</button></div>
<main id="content"></main>
<script>
const CASES = __CASES__;
const sel=document.getElementById('case'), content=document.getElementById('content');
const startedAt=new Date().toISOString();
const decisions={};
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function pickKey(type,id){return `${sel.value}:${type}:${id}`;}
function card(type,row,detail){
  const key=pickKey(type,row.id), saved=decisions[key]||{};
  const options=['영향/검토 필요','해당 없음','판단 보류'];
  return `<section class="card ${row.suggested?'candidate':''}" data-key="${escapeHtml(key)}"><strong>${escapeHtml(row.id)}</strong> <span class="meta">${escapeHtml(detail)} · 시스템 후보: ${row.suggested?'예':'아니오'}</span>
  <div class="text">${escapeHtml(type==='change'?row.before:row.text)}</div>
  ${type==='change'?`<details><summary>수정 후 내용 보기</summary><div class="after">${escapeHtml(row.after)}</div></details>`:''}
  ${type==='ip'&&row.premise?`<div class="meta">이전 판단 전제: ${escapeHtml(row.premise)}</div>`:''}
  <div class="choices">${options.map((v,i)=>`<label><input type="radio" name="${escapeHtml(key)}" value="${i}" ${saved.choice===String(i)?'checked':''}>${v}</label>`).join('')}</div>
  <textarea class="reason" placeholder="판단 이유 또는 추가 확인할 정보">${escapeHtml(saved.reason||'')}</textarea></section>`;
}
function saveVisible(){document.querySelectorAll('.card').forEach(el=>{const key=el.dataset.key;const choice=el.querySelector('input[type=radio]:checked');const reason=el.querySelector('textarea').value; if(choice||reason)decisions[key]={choice:choice?.value??null,reason};});}
function render(){const c=CASES.find(x=>x.id===sel.value);content.innerHTML=`<h2>B-3 · ${escapeHtml(c.change)}</h2><p>변경 영향을 받는 자료인지 판단하세요. 수정 후 내용은 영향 여부를 정한 뒤 열어보세요.</p>`+
 c.artifacts.map(x=>card('change',x,x.kind)).join('')+
 `<h2>D · ${escapeHtml(c.release)}</h2><p>IP 담당자에게 검토 요청할 사건인지 판단하세요.</p>`+
 c.events.map(x=>card('ip',x,x.record)).join('');}
CASES.forEach(c=>sel.add(new Option(c.id,c.id))); sel.addEventListener('change',()=>{saveVisible();render();});render();
document.getElementById('download').addEventListener('click',()=>{saveVisible();const result={schema:'topic-review-v1',reviewer:document.getElementById('reviewer').value||'anonymous',started_at:startedAt,exported_at:new Date().toISOString(),cases:CASES.map(c=>({id:c.id,sha256:c.sha256})),decisions};const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`topic-review-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);});
</script></body></html>'''


def main() -> None:
    cases = [public_case(name) for name in ("fixtures.json", "fixtures_followup.json")]
    payload = json.dumps(cases, ensure_ascii=False).replace("<", "\\u003c")
    page = PAGE.replace("__CASES__", payload)
    output = HERE / "site"
    output.mkdir(exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    print(output / "index.html")


if __name__ == "__main__":
    main()
