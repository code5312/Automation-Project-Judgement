# patent-evidence-poc

사람 판단 중심 지식재산 업무자동화 후보 중 **선행기술 Evidence Copilot**의 최소 검증 PoC입니다.

목표는 처음부터 LLM이나 UI를 붙이는 것이 아니라 다음 질문에 먼저 답하는 것입니다.

> "단순한 검색 baseline이 실제 인용문헌을 Top-K 안에 얼마나 회수할 수 있는가?"

## 현재 범위

1. 특허 문서의 최소 스키마 정의
2. 고정 fixture corpus / 평가셋
3. 결정론적 BM25 baseline
4. Recall@K / MRR 평가
5. JSON / Markdown 결과 리포트

현재 `data/*_fixture.jsonl`은 **파이프라인 검증용 합성 데이터**입니다.
실제 KIPRIS 특허/심사인용문헌 데이터로 성능을 주장하기 위한 평가셋이 아닙니다.

2026-09-28 현재 KIPRIS 실 API 10건 파일럿에서 공보·인용문헌 조회와 국내 공보 재연결을 확인했습니다. **실데이터 검색 성능은 아직 측정하지 않았습니다.** 진행 경과와 한계는 [개인 작업기록](docs/personal_worklog.md)에 정리했습니다.

## 왜 이 순서인가

최종 서비스 후보는 다음 흐름을 목표로 합니다.

```
기술 설명/청구항
→ 기술요소 분해
→ 선행특허 검색
→ Top-K 재랭킹
→ 기술요소별 Evidence Matrix
→ 사람 검토
→ 피드백 반영 재검색
```

하지만 먼저 아래 baseline을 고정합니다.

```
query
→ BM25
→ ranked patent ids
→ citation proxy labels with an explicit type policy
→ Recall@K / MRR
```

이 baseline을 넘어서는 개선이 확인된 뒤 임베딩, reranker, LLM을 추가합니다.

## 실행

Python 3.11+ / 외부 패키지 없음.

```bash
cd patent-evidence-poc
python -m src.patent_evidence.cli \
  --corpus data/corpus_fixture.jsonl \
  --eval data/eval_fixture.jsonl \
  --out output
```

결과:
- `output/baseline_results.json`
- `output/baseline_report.md`

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 실제 데이터로 넘어갈 때

`docs/data_plan.md`의 KIPRISPlus 매핑을 따라 실제 데이터를 수집합니다.

핵심 원칙:
- 실제 KIPRIS 데이터와 합성 데이터를 섞어 표시하지 않기
- 심사 인용문헌을 gold label로 쓰되 "인용되지 않음 = 무관함"으로 단정하지 않기
- baseline 성능이 낮아도 숨기지 않고 이후 개선폭을 기록하기
- API 인증키는 환경변수/로컬 설정으로만 관리하고 Git에 커밋하지 않기

### 첫 실제 응답 점검

KIPRISPlus 키가 준비되면 `KIPRIS_API_KEY`를 현재 셸의 환경변수로 설정하고 다음을 실행합니다. 키를 명령 인수나 Git 파일에 넣지 않습니다.

```bash
python scripts/inspect_kipris_case.py 1019950039253
```

스크립트는 `data/raw/<출원번호>.citation.xml`에 원본 인용 응답을 저장하고, 인용 필드명·구분값 분포·국내 문헌 조회 키를 출력합니다. `data/raw/`는 Git에서 제외됩니다. 원본을 다시 분석할 때는 키 없이 실행할 수 있습니다.

```bash
python scripts/inspect_kipris_case.py 1019950039253 --citation-xml data/raw/1019950039253.citation.xml
```

실제 구분값의 뜻을 공식 명세와 대조하기 전에는 인용 목록을 평가 정답으로 사용하지 않습니다.

이미 저장한 질의 4건의 국내 인용 공보를 중복 없이 재조회하려면 다음을 실행합니다. 결과는 Git에서 제외되는 `data/raw/pilot_document_linkage.json`에 저장됩니다.

```bash
python scripts/fetch_pilot_documents.py 1020140170841 1020060037777 1020090012972 1020110090313
```

이 파일의 E0802·E0805는 **선행기술조사 관련 인용 proxy**일 뿐 심사관 최종 정답이 아닙니다.
