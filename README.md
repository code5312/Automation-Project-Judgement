# 사람 판단 중심 IP 업무 자동화

KIPRIS Plus의 실제 특허 데이터를 검색·점수화해 사람이 먼저 검토할 후보의 우선순위를 보여주고, 사람의 판단을 이유와 함께 기록하는 도구다. 가짜 특허 데이터를 생성하지 않으며, 최종 판단은 항상 사람이 한다. 전체 설계는 [docs/DESIGN.md](docs/DESIGN.md), 진행 단계는 [docs/PIPELINE.md](docs/PIPELINE.md), 확인이 필요한 외부 사실은 [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)를 참고한다.

이 저장소는 현재 **단계 0(정리)** 구조로 이행 중이다. 판단 저장은 아직 `data/judgments.json` append 방식이고(단계 1에서 SQLite로 이관), 점수 개념/가중치는 아직 코드 상수다(단계 2에서 YAML로 분리).

## 설치와 실행

Python 3.12 이상이 필요하다.

```powershell
pip install -e ".[dev]"
$env:KIPRIS_ACCESS_KEY = "YOUR_ACCESS_KEY"
streamlit run app/streamlit_app.py
```

CLI로 직접 검색·CSV 저장을 하려면:

```powershell
python -m ipauto.cli search "battery" --technology "전기차 배터리 냉각" --debug
```

## 환경 변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `KIPRIS_ACCESS_KEY` | 필수 | KIPRIS Plus freeSearchInfo 접근키. 코드·로그·오류 메시지에는 절대 원문으로 남지 않는다(URL 인코딩된 형태까지 마스킹). |
| `KIPRIS_BASE_URL` | 선택 | KIPRIS 엔드포인트 재정의용. HTTPS 지원 여부가 아직 미확인이라 기본값은 http 엔드포인트다(docs/OPEN_QUESTIONS.md 참고). |

`.env.example`을 참고해 로컬 `.env` 파일을 만들 수 있으나, 이 프로젝트는 `.env` 파일을 자동 로드하지 않는다. 셸 환경변수로 직접 설정해야 한다.

## 디렉터리 구조 (단계 0 기준)

```
src/ipauto/
  config.py          환경변수 로드, 키 마스킹
  connectors/kipris.py   KIPRIS 호출·XML 파싱(defusedxml)·오류 분류
  scoring/           ipc.py, keywords.py, bands.py — 관련도 점수·구간
  judgments/         service.py(JSON 저장, 사유 필수 검증), compare.py
  triage/ cards/ watch/   단계 3·4용 빈 인터페이스(아직 미구현)
  cli.py             디버깅용 CLI 진입점
app/streamlit_app.py 검색 화면 + 판단 기록 폼
tests/               단위 테스트 + fixtures/(모두 샘플 데이터, 실제 KIPRIS 응답 아님)
```

## 점수는 법적 판단이 아니다

관련도 점수와 우선순위는 사람이 먼저 검토할 특허를 정렬하기 위한 보조 지표일 뿐이며, 선행특허 여부·등록 가능성·침해 여부에 대한 법적 판단이나 법률 자문이 아니다. 최종 IP 조치 판단은 항상 사람이 내린다.

## 알려진 한계 (단계 0 기준)

- 검색은 검색어 1개, 최대 20건까지만 가져온다(다중 검색어·페이지네이션은 단계 2).
- 개념 그룹·가중치·IPC 규칙이 아직 코드 상수다(YAML 설정 분리는 단계 2).
- 판단 기록이 아직 JSON 파일 append 방식이라 동시 저장 시 유실 위험이 있다(SQLite 트랜잭션 이관은 단계 1).
- 화면에 100점 만점 점수가 그대로 노출된다(3단계 구간만 표시하도록 바꾸는 것은 단계 2).
- 사건 감지·트리아지·판단 카드·전제 감시·Jira 연동은 아직 없다(단계 3~5).
