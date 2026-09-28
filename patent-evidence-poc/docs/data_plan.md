# 실제 KIPRISPlus 데이터 전환 계획

## 1. 공식 API에서 확인된 데이터

KIPRISPlus의 **특허·실용 공개·등록공보 REST API**는 검색뿐 아니라 서지정보 영역에서 다음 항목을 별도로 제공합니다.

- IPC 정보
- CPC 정보
- 초록
- 청구항
- 선행기술조사문헌
- 공개/공고 전문 PDF 경로

또한 **특허·실용 심사인용문헌 REST API**가 별도 서비스로 운영되고 있습니다.

따라서 실제 평가셋은 다음 형태를 목표로 합니다.

```json
{
  "case_id": "KR-APPLICATION-NO",
  "query": "title + abstract 또는 독립청구항",
  "ipc": ["..."],
  "cpc": ["..."],
  "gold_doc_ids": ["심사 인용문헌 ..."]
}
```

## 2. 인증

KIPRISPlus Open API는 인증키가 필요한 서비스입니다.

- `openapi/rest/**` 계열은 예시 문서에서 `accessKey`를 사용
- 실제 키는 Git에 저장하지 않음
- 환경변수 예: `KIPRIS_ACCESS_KEY`

서비스 신청/승인 여부와 호출 제한은 실제 계정에서 확인해야 합니다.

## 3. 1차 실제 평가셋 목표

처음부터 대규모 수집하지 않고 **20~50건**으로 고정합니다.

선정 조건:
1. 국내 특허/실용
2. 초록 또는 청구항 텍스트 확보 가능
3. 심사 인용문헌이 1건 이상 존재
4. 인용문헌 식별자를 후보 corpus와 연결할 수 있음

저장 구조:
- `data/real/corpus.jsonl`
- `data/real/eval.jsonl`
- 원 API 응답은 `data/raw/`에 저장하되 Git에는 커밋하지 않음

## 4. baseline 실험

### B0
- query: 제목 + 초록
- corpus: 제목 + 초록
- retrieval: BM25

### B1
- query: 독립청구항
- corpus: 제목 + 초록 + 독립청구항
- retrieval: BM25

### B2
- B1 + IPC/CPC 동일/인접 분류 boost

이 세 개를 먼저 비교한 뒤 임베딩을 추가합니다.

## 5. 지표 해석 주의

심사관 인용문헌은 좋은 gold signal이지만 완전한 relevance label은 아닙니다.

- 인용되지 않은 문헌이 반드시 무관한 것은 아님
- 심사 목적/시점에 따라 인용 집합이 달라질 수 있음
- 따라서 초기 지표는 **examiner-citation retrieval benchmark**라고 표현

주요 지표:
- Recall@10 / @20 / @50
- MRR
- 필요 시 nDCG

## 6. 다음 개선 순서

```
BM25
→ IPC/CPC filter or boost
→ Korean embedding
→ cross-encoder reranker
→ LLM 기술요소 분해
→ Evidence Matrix
→ 사람 relevance feedback
```

각 단계마다 동일 평가셋으로 전후 성능을 비교합니다.

## 7. 공식 확인 출처

- KIPRISPlus 특허·실용 공개·등록공보 서비스 상세
- KIPRISPlus Open API 상태 페이지
- KIPRISPlus Open API 이용약관/인증키 절차
- KIPRISPlus 심사인용문헌 REST API

공식 페이지의 세부 endpoint는 실제 API 신청 후 최신 명세서와 대조해 코드에 고정합니다.
