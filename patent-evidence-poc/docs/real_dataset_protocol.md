# KIPRIS 실제 평가셋 구성 프로토콜 v0.1

## 목적

처음부터 대규모 특허 검색 시스템을 만드는 것이 아니라, **국내 특허 20~50건의 고정 평가셋**으로 검색 baseline을 검증한다.

## 확인된 KIPRISPlus 연결 구조

### 기준 특허
출원번호(applicationNumber)를 평가 case의 기본 ID로 사용한다.

공개·등록공보 서비스에서 확인할 정보:
- 발명의 명칭
- 초록
- 출원번호
- 공개번호
- 등록번호
- IPC
- CPC
- 청구항

### gold signal
특허·실용 심사인용문헌 서비스에서 기준 출원번호의 인용문헌을 가져온다.

KIPRISPlus 공식 지원 답변에서 안내한 국내 문헌 연결 규칙:
- 표준인용문헌국가코드 = KR
- 표준인용식별코드 첫 글자 A/U → 표준인용문헌번호를 open number로 조회
- 표준인용식별코드 첫 글자 B/Y → 표준인용문헌번호를 공고/등록번호 계열로 조회
- 해외 문헌은 V1 평가셋에서 제외하고 별도 통계로 남김

## 왜 국내 인용만 먼저 쓰나

20~50건 PoC에서 KR/US/EP/JP 등 여러 공보 체계를 한꺼번에 정규화하면 데이터 엔지니어링이 검색 실험보다 커진다.

따라서 V1은:
- query patent: 한국 특허
- gold citation: KR 문헌만
- corpus: gold KR 문헌 + 같은 기술분류의 후보/negative 문헌

으로 제한한다.

## case 선정 기준

포함:
1. 특허(실용신안은 V1 제외)
2. 제목/초록이 비어 있지 않음
3. 청구항을 조회할 수 있음
4. 심사인용문헌이 1건 이상 존재
5. 그중 KR A/U/B/Y 표준 인용문헌을 최소 1건 실제 공보로 다시 연결할 수 있음

제외:
- 인용정보가 없거나 표준화 번호가 없는 case
- 텍스트가 사실상 비어 있는 오래된 공보
- KR gold를 하나도 연결하지 못한 case

## 20~50건 뽑는 방법

특정 기술 한 분야에 과적합되지 않도록 IPC 대분류를 최소 3개로 나눈다.

1차 권장:
- G06 계열: 컴퓨팅/데이터 처리
- H01 계열: 전기/반도체
- G01 계열: 측정/센서

각 그룹에서 7~15개 case를 모아 총 20~50개를 구성한다.

**중요:** 이 분류는 최종 프로젝트 도메인을 반도체로 고정하려는 것이 아니라 검색 baseline이 서로 다른 기술 문맥에서도 동작하는지 보기 위한 샘플링 층이다.

## corpus 구성

Recall@K를 의미 있게 만들려면 gold 문헌만 20~50개 넣으면 안 된다.

V0:
- 모든 case의 KR gold 문헌 합집합
- 각 query의 IPC/CPC 인접 검색 결과에서 distractor 추가
- 전체 corpus 최소 수백 건을 목표

무료 월 1,000회 호출을 고려해 raw XML 응답을 data/raw/에 캐시하고 같은 API를 반복 호출하지 않는다.

## 산출물

data/real/eval.jsonl
- case_id
- query_title
- query_abstract
- query_claim_1
- ipc
- cpc
- gold_doc_ids

data/real/corpus.jsonl
- doc_id
- application_number
- open_number
- register_number
- title
- abstract
- independent_claim
- ipc
- cpc
- source=KIPRISPlus

## 평가

B0: 제목 + 초록 → BM25  
B1: 독립청구항 → BM25  
B2: B1 + IPC/CPC boost

지표:
- Recall@10 / 20 / 50
- MRR
- case별 검색 실패 분석

### 해석상 주의
심사 인용문헌은 **완전한 relevance 정답이 아니라 examiner-citation gold signal**이다.
인용되지 않은 문헌이 무관하다는 뜻은 아니다.

## API 키/비용

KIPRISPlus는 회원 가입 → 서비스 선택/신청 → 관리자 승인 → APIKEY 확인 절차를 안내한다.
Open API는 월 1,000회까지 무료이며, 대학·연구기관은 신청 전 담당자 문의를 권장한다.

API 키는 Git에 커밋하지 않는다.
- KIPRIS_SERVICE_KEY: kipo-api/kipi 공개·등록공보 호출용
- KIPRIS_ACCESS_KEY: CitationService 호출용(활성화된 계정 명세에 따라 실제 키 체계 확인)

## 첫 실제 smoke test

공식 KIPRISPlus 문의 사례에 등장한 다음 출원번호를 **연결 로직 점검용**으로만 사용한다.
- 1019950039253
- 1020140170841

이 번호들은 benchmark 성능 평가용으로 선정한 것이 아니다.

## API 활성화 뒤 바로 할 일

1. 두 smoke case의 applicationNumberSearchInfo 조회
2. citation 응답 원본 저장
3. KR A/U/B/Y citation만 변환
4. open/register number로 공보 재조회
5. query ↔ citation 링크가 실제로 이어지는지 수동 확인
6. 성공하면 20~50건 수집기로 확장
