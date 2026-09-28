# 진행 기록

## Stage 0 · baseline scaffold

### 목표
실제 KIPRIS API 연결 전에 **검색 → 랭킹 → gold citation 평가 → 리포트** 전체 흐름이 재현 가능하게 동작하는지 확인한다.

### 구현
- 특허 corpus / 평가셋 JSONL 스키마
- 외부 패키지 없는 결정론적 BM25
- Recall@K / MRR
- JSON / Markdown 결과 리포트
- 합성 fixture corpus 8건
- 합성 평가 query 3건
- unittest

### fixture smoke test 결과

합성 fixture 기준 예상 결과:

| metric | value |
| --- | ---: |
| Recall@1 | 0.6667 |
| Recall@3 | 1.0000 |
| Recall@5 | 1.0000 |
| Recall@10 | 1.0000 |
| Recall@20 | 1.0000 |
| MRR | 1.0000 |

케이스별:
- FIX-Q-001: gold 2건 중 Top-1에서 1건, Top-3에서 2건 모두 회수
- FIX-Q-002: gold 2건 중 Top-1에서 1건, Top-3에서 2건 모두 회수
- FIX-Q-003: gold 1건이 Top-1

> **주의:** 이 숫자는 실제 특허 검색 성능이 아니다. query와 fixture 문서를 의도적으로 구분 가능하게 만든 smoke test이므로, 실제 KIPRIS 데이터가 들어오면 크게 달라질 수 있다.

### 다음 체크포인트
1. KIPRISPlus API 인증키/서비스 신청 상태 확인
2. 실제 특허 20~50건 선정
3. 심사 인용문헌 식별자와 corpus 문헌 ID 연결
4. 동일 BM25 코드로 B0 실제 baseline 측정
5. B1(독립청구항), B2(IPC/CPC boost) 순차 비교
6. baseline 결과가 확보된 뒤에만 embedding / reranker / LLM을 추가

### 공식 API 확인 메모
2026-09-28 확인 기준 KIPRISPlus API 상태 페이지에서 다음 REST API가 정상 운영으로 표시됨.
- 특허·실용 공개·등록공보
- 특허·실용 심사인용문헌

실제 endpoint 및 응답 필드는 서비스 신청 후 최신 통합 명세서와 다시 대조한다.
