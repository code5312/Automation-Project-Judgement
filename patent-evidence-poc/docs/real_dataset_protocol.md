# KIPRIS 실제 평가셋 구성 프로토콜 v0.2

## 목적

처음부터 대규모 특허 검색 서비스를 만드는 것이 아니라, **국내 특허 20~50건의 고정 평가셋**으로 검색 baseline과 개선폭을 검증한다.

이 평가셋이 증명하려는 것은 "법적으로 올바른 선행기술 판단"이 아니다.

> **한국 특허 공개데이터에서 과거 심사·인용 과정에 등장한 관련 문헌을 검색 시스템이 얼마나 잘 회수하는가**

를 재현 가능한 방식으로 측정하는 것이 1차 목표다.

## 확인된 KIPRISPlus 데이터 구조

### 기준 특허
출원번호(applicationNumber)를 평가 case의 기본 ID로 사용한다.

공개·등록공보 API에서 확인할 정보:
- 발명의 명칭
- 초록
- 출원번호
- 공개번호
- 등록번호
- IPC
- CPC
- 청구항

### 인용 데이터
KIPRISPlus 상품 카탈로그의 **특허·실용 인용문헌**은 출원인이 기재하거나 심사관이 참조한 인용문헌 정보를 함께 표준화해 제공한다.

따라서 **모든 인용문헌을 자동으로 examiner gold label로 취급하면 안 된다.**

반드시 raw 응답에서 인용 출처/구분 필드를 보존하고, 실제 샘플을 확인한 뒤 다음처럼 gold policy를 명시한다.

- Gold-A: 심사관 최종 심사에서 사용된 것으로 확인되는 인용만
- Gold-B: 선행기술조사/심사 과정의 인용까지 포함
- Reference-only: 출원인 기재 인용 등은 평가 정답에서 제외하되 참고 데이터로 보존

**정확한 코드값/명칭은 API 키 활성화 후 raw XML 20건 이상을 먼저 관찰해 확정한다.**
코드에서는 citation division whitelist 없이는 gold를 만들 수 없도록 한다.

## 국내 문헌 연결 규칙

KIPRISPlus 공식 지원 답변에서 안내한 국내 문헌 연결 방식:
- 표준인용문헌국가코드 = KR
- 표준인용식별코드 첫 글자 A/U → 표준인용문헌번호를 open number로 조회
- 표준인용식별코드 첫 글자 B/Y → 표준인용문헌번호를 공고/등록번호 계열로 조회

해외 문헌은 V1에서 제외하고 통계만 남긴다.

## 왜 국내 인용만 먼저 쓰나

20~50건 PoC에서 KR/US/EP/JP 공보 정규화를 동시에 처리하면 데이터 엔지니어링이 검색 실험보다 커진다.

V1:
- query patent: 한국 특허
- gold candidate: KR 인용문헌
- gold label: 명시한 citation-origin policy를 통과한 문헌만
- corpus: gold KR 문헌 + 같은 기술분류의 후보/negative 문헌

## case 선정 기준

포함:
1. 특허
2. 제목/초록 확보
3. 청구항 조회 가능
4. 인용문헌 1건 이상
5. KR A/U/B/Y 표준 인용문헌을 최소 1건 실제 공보로 재연결 가능
6. gold policy 적용 후 gold가 최소 1건 남음

제외:
- 인용정보가 없거나 표준화 번호가 없는 case
- 텍스트가 사실상 비어 있는 오래된 공보
- KR 인용을 실제 공보로 연결하지 못한 case
- 인용 출처를 구분할 수 없어 gold 정의가 불가능한 case

## 20~50건의 역할

20~50건은 최종 성능을 일반화하기 위한 대규모 benchmark가 아니다.

용도:
- 데이터 연결 가능성 검증
- baseline이 너무 쉬운지/어려운지 확인
- B0/B1/B2 상대 비교
- 실패 유형 수집
- 8주 프로젝트에서 확장할 가치가 있는지 결정

따라서 발표에서 "전체 한국 특허에서 성능 X%"라고 일반화하지 않는다.

## 샘플링

특정 한 분야에만 맞춰지지 않도록 1차 exploratory set은 IPC 대분류 최소 3개로 분산한다.

권장 시작점:
- G06: 컴퓨팅/데이터 처리
- H01: 전기/반도체
- G01: 측정/센서

각 그룹 7~15건, 총 20~50건.

이후 최종 도메인이 정해지면 별도의 domain-focused eval set을 추가한다.

## corpus 구성

gold 문헌만 넣으면 Recall@K가 지나치게 쉬워진다.

V0:
- 모든 case의 gold 문헌 합집합
- 각 query의 IPC/CPC 인접 검색 결과에서 distractor 추가
- 전체 corpus 최소 수백 건

가능하면 "랜덤 negative"보다 **같은 IPC/CPC인데 실제 gold는 아닌 hard negative**를 우선 사용한다.

## 평가

### B0
- query: 제목 + 초록
- corpus text: 제목 + 초록
- retrieval: BM25

### B1
- query: 독립청구항
- corpus text: 제목 + 초록 + 독립청구항
- retrieval: BM25

### B2
- B1 + IPC/CPC filter 또는 boost

지표:
- Recall@10 / 20 / 50
- MRR
- case별 실패 분석
- gold-origin별 성능 분리(가능한 경우)

### 지표 해석
이 benchmark는 **examiner/citation retrieval proxy**다.

- 인용되지 않은 문헌이 무관하다는 뜻이 아니다.
- 법적 신규성·진보성 판단 정확도를 측정하지 않는다.
- 심사관/출원인/조사 출처가 섞인 데이터를 정제하지 않으면 평가 자체가 왜곡될 수 있다.

## 경쟁 서비스 대비 포지셔닝

이미 존재:
- KIPRIS 유사특허 검색
- WIPO PATENTSCOPE AI-Assisted Search
- Patsnap Novelty Search

따라서 차별점을 "AI 특허 검색"으로 주장하지 않는다.

프로젝트 수준의 차별화 가설:
1. 한국 공개데이터 기반 재현 가능한 benchmark
2. baseline → 개선 모델의 정량 비교
3. 기술요소별 evidence mapping
4. 사람의 관련/무관 피드백이 다음 검색 결과를 어떻게 개선하는지 측정
5. 결과뿐 아니라 실패 사례와 출처를 투명하게 보여주는 검증 중심 workflow

이 가설도 최종 차별점으로 확정하지 않고 사용자/멘토 검증 대상으로 둔다.

## 멘토/제3자 통과 기준

다음 질문에 답을 못 하면 구현을 확장하지 않는다.

1. **왜 이 인용문헌을 정답이라고 부를 수 있는가?**
   - citation origin을 구분하고 proxy라는 한계를 명시해야 통과.

2. **Patsnap/WIPO/KIPRIS와 무엇이 다른가?**
   - 기능 존재 여부가 아니라 "재현 가능한 한국어 평가 + evidence + feedback improvement"를 실제 수치로 보여줘야 통과.

3. **20~50건으로 의미가 있는가?**
   - 최종 일반화 성능이 아니라 feasibility/baseline 결정용 exploratory set임을 명확히 해야 통과.

4. **AI를 빼면 무엇이 남는가?**
   - BM25/IPC baseline만으로도 평가 파이프라인이 작동해야 통과.

5. **LLM이 정말 필요한가?**
   - baseline 실패 유형에서 기술요소 분해/동의어/문맥 재랭킹 문제가 확인된 경우에만 도입.

6. **사람 판단은 어디에 남는가?**
   - 시스템은 관련 문헌과 근거를 제공하고, 법적 신규성/진보성/출원 전략은 사람이 결정.

## API 키/비용

KIPRISPlus Open API는 기본 무료 호출이 월 1,000회 제공되고 무료분 소진 시 자동 결제되지 않는다.

반복 실험은:
API 호출 → raw XML cache → normalization → local experiments

구조로 운영한다.

API 키는 Git에 커밋하지 않는다.

## API 활성화 직후 첫 smoke test

공식 문의 사례에 등장했던 출원번호:
- 1019950039253
- 1020140170841

목적은 benchmark가 아니라 **citation → 실제 공보 연결 및 필드 관찰**이다.

순서:
1. 기준 특허 조회
2. citation raw XML 저장
3. citation division 값 분포 출력
4. KR A/U/B/Y 문헌 재조회
5. 출처/번호/제목을 사람이 수동 확인
6. gold policy 초안 확정
7. 5~10건으로 재검증
8. 문제가 없을 때만 20~50건으로 확대
