# 평가 세트 (docs/PIPELINE.md 단계 2)

## `ev_battery_cooling_v1.json`

**이 파일의 라벨은 AI(Claude)가 예시로 작성한 초안이며, 사람이 검증하기 전까지 진짜 평가 기준으로 쓸 수 없다.** 사용자가 "일단 예시로 라벨링을 달아달라"고 요청해 작성한 워크플로 시범용 데이터다. `docs/PIPELINE.md` 단계 2의 "평가 세트 20~50건 라벨링 (사람 판단 기준)" 체크박스는 이 파일만으로는 체크하지 않는다.

- **특허 데이터 자체는 실제 데이터다.** `outputs/kipris_patents_*.csv`(2026-09-28, 실제 KIPRIS Plus 호출 결과, 검색어 "전기차 배터리 냉각")를 출원번호 기준으로 중복 제거해 40건을 추렸다. 가짜 특허 데이터는 생성하지 않는다는 원칙(`README.md`)을 지켰다.
- **라벨(`human_label`, `label_rationale`)은 AI가 제목·초록·IPC를 읽고 독립적으로 판단한 것**이며, 시스템이 그 CSV를 생성할 때 매긴 `relevance_score`/`review_priority`를 그대로 베낀 게 아니다(베끼면 시스템이 자기 자신을 검증하는 순환 논리가 된다).
- 라벨은 "전기차 배터리 냉각"이라는 `review_technology` 기준으로만 판단했다. 배터리 일반·전기차 일반 특허라도 냉각/열관리가 핵심이 아니면 낮음으로 분류했다.

### 다음에 할 일

1. 실제 담당자가 이 40건(또는 새로 뽑은 세트)을 검토해 `human_label`/`label_rationale`을 확정하거나 고친다.
2. 확정되면 `docs/PIPELINE.md` 단계 2 체크박스를 체크하고, 이 README의 안내문을 지운다.
3. `python -m ipauto.cli evaluate`로 기준선을 다시 측정해 `docs/PIPELINE.md`의 "평가 지표 기록" 표에 공식 기준선으로 기록한다.

### 형식

```json
[
  {
    "발명의 명칭": "...", "출원번호": "...", "출원인": "...", "IPC": "...",
    "등록상태": "...", "초록": "...",
    "review_technology": "전기차 배터리 냉각",
    "human_label": "높음 | 보통 | 낮음",
    "label_rationale": "라벨을 매긴 이유 한 줄"
  }
]
```

`python -m ipauto.cli evaluate [평가세트.json]`으로 현재 스코어러의 `review_priority`와 `human_label`을 비교해 정확도·혼동행렬을 출력한다(`src/ipauto/evaluation.py`).
