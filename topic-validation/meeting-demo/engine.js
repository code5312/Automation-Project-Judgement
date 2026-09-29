/* Deterministic meeting demo rules. They are examples, not field-validated models. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.DEMO_ENGINE = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  function exceptionDecision(event, approved) {
    if (!event.consent) return {status: 'manual', action: '발급 중단 · 동의 상태 확인', reason: '수신 동의가 없어 과거 재발급 규칙을 적용할 수 없습니다.'};
    if (!['grade_missing', 'grade_sync_delay'].includes(event.type))
      return {status: 'manual', action: '담당자 확인', reason: '같은 조건의 검증된 해결 이력이 없습니다.'};
    if (!approved) return {status: 'approval', action: 'CRM 등급 재조회 후 재발급 제안', reason: '유사한 성공 이력 2건이 있으나 자동 적용 승인이 필요합니다.'};
    return {status: 'ready', action: 'CRM 등급 재조회 후 재발급', reason: '이 회의 사례의 승인 범위 안에 있습니다. 실제 실행은 하지 않습니다.'};
  }

  function conflicts(existing, incoming) {
    const findings = [];
    for (const prior of existing) {
      if (prior.trigger !== incoming.trigger) continue;
      for (const [field, value] of Object.entries(incoming.writes || {})) {
        if (Object.hasOwn(prior.writes || {}, field) && prior.writes[field] !== value)
          findings.push({kind: '쓰기-쓰기', with: prior.name, detail: `${field}: ${prior.writes[field]} ↔ ${value}`});
        if ((prior.reads || []).includes(field))
          findings.push({kind: '읽기-쓰기', with: prior.name, detail: `${field}의 읽기 결과가 실행 순서에 좌우될 수 있음`});
      }
      if (incoming.effect && incoming.effect === prior.effect)
        findings.push({kind: '중복 실행', with: prior.name, detail: `${incoming.effect} 동작이 두 번 발생할 수 있음`});
    }
    return findings;
  }

  function canonical(text) {
    return String(text || '').toLowerCase().replace(/오만\s*원/g, '50000원')
      .replace(/삼만\s*원/g, '30000원').replace(/([35])\s*만\s*원/g, (_, n) => `${n}0000원`)
      .replace(/일주일/g, '7일').replace(/[,\s_]/g, '');
  }
  function changeState(after, oldForms, newForms) {
    const body = canonical(after);
    const hasOld = oldForms.some(x => body.includes(canonical(x)));
    const hasNew = newForms.some(x => body.includes(canonical(x)));
    if (hasOld && !hasNew) return {state: 'stale', reason: '변경 전 값이 남아 있습니다.'};
    if (hasNew && !hasOld) return {state: 'updated', reason: '변경 후 값이 확인됩니다.'};
    if (hasNew && hasOld) return {state: 'mixed', reason: '변경 전후 값이 함께 있어 문맥 확인이 필요합니다.'};
    return {state: 'uncertain', reason: '값이 명시되지 않아 사람이 확인해야 합니다.'};
  }

  function ipSignal(event) {
    const text = event.text || '';
    const exposure = /외부|SDK|오픈소스|고객용|고객 단말|플러그인|공개 API|논문|학회/.test(text);
    const technical = /엔진|모델|알고리즘|기술|방법|로직|규칙/.test(text);
    const novel = /새로운|신규|새 /.test(text);
    if (event.record === 'trade_secret' && exposure)
      return {state: 'review', reason: '과거 비공개 판단의 외부 노출 전제가 달라질 수 있습니다.', premise: true};
    if (event.record === 'none' && novel && technical)
      return {state: 'review', reason: '새 기술로 보이며 기존 IP 검토 기록이 없습니다.', premise: false};
    if (technical && (exposure || event.record === 'none'))
      return {state: 'hold', reason: '기술 범위 또는 공개 내용을 추가 확인해야 합니다.', premise: false};
    return {state: 'skip', reason: '현재 입력만으로는 검토 요청 신호가 보이지 않습니다.', premise: false};
  }
  return {exceptionDecision, conflicts, canonical, changeState, ipSignal};
});
