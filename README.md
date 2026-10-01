# 사람 판단 중심 IP 업무 자동화

KIPRIS Plus의 실제 특허 데이터를 검색·점수화해 사람이 먼저 검토할 후보의 우선순위를 보여주고, 사람의 IP 조치 판단을 이유·전제와 함께 append-only로 기록하는 도구다. 가짜 특허 데이터를 생성하지 않으며, 최종 판단은 항상 사람이 한다. 전체 설계는 [docs/DESIGN.md](docs/DESIGN.md), 진행 단계는 [docs/PIPELINE.md](docs/PIPELINE.md), 확인이 필요한 외부 사실은 [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)를 참고한다.

이 저장소는 현재 **단계 1(데이터 모델)** 을 완료했고, **단계 2(수집·순위)** 중 다중 검색어·페이지네이션·출원번호 중복 제거, 개념 그룹·가중치·IPC 규칙 YAML 설정 분리까지 반영했다.

## 설치와 실행

Python 3.12 이상이 필요하다.

```powershell
pip install -e ".[dev]"
$env:KIPRIS_ACCESS_KEY = "YOUR_ACCESS_KEY"
streamlit run app/streamlit_app.py
```

처음 실행하거나 예전 `data/judgments.json` 판단 기록이 있다면, 실행 전에 SQLite로 1회 이관한다(재실행해도 중복 없이 안전하다):

```powershell
python -m ipauto.cli migrate-judgments
```

CLI로 직접 검색·CSV 저장을 하려면(검색어는 여러 개를 공백으로 구분해 전달할 수 있으며, 결과는 출원번호 기준으로 중복 제거된다):

```powershell
python -m ipauto.cli search "battery" "cooling" --technology "전기차 배터리 냉각" --debug
```

## 환경 변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `KIPRIS_ACCESS_KEY` | 필수 | KIPRIS Plus freeSearchInfo 접근키. 코드·로그·오류 메시지에는 절대 원문으로 남지 않는다(URL 인코딩된 형태까지 마스킹). |
| `KIPRIS_BASE_URL` | 선택 | KIPRIS 엔드포인트 재정의용. HTTPS 지원 여부가 아직 미확인이라 기본값은 http 엔드포인트다(docs/OPEN_QUESTIONS.md 참고). |
| `IPAUTO_DB_PATH` | 선택 | SQLite 파일 경로 재정의용. 기본값은 `data/ipauto.db`(커밋되지 않음). |
| `IPAUTO_CONFIG_DIR` | 선택 | 개념 그룹·가중치·IPC 규칙 YAML 디렉터리 재정의용. 기본값은 `config/`. |

`.env.example`을 참고해 로컬 `.env` 파일을 만들 수 있으나, 이 프로젝트는 `.env` 파일을 자동 로드하지 않는다. 셸 환경변수로 직접 설정해야 한다.

## 디렉터리 구조

```
config/
  concepts.yaml      개념 그룹·가중치·보너스 설정
  ipc_rules.yaml      IPC 패밀리·개념-IPC 매핑 설정
src/ipauto/
  config.py          환경변수 로드, 키 마스킹
  connectors/kipris.py   KIPRIS 호출(fetch_all: 다중 검색어·페이지네이션)·XML 파싱(defusedxml)·오류 분류
  scoring/           ipc.py, keywords.py, bands.py — 관련도 점수·구간, rules.py — config/*.yaml 로더
  db/                schema.sql, connection.py, repositories.py — SQLite 저장소
  judgments/         service.py(게이트 B 검증), compare.py(집합 비교), migrate_json.py
  triage/ cards/ watch/   단계 3·4용 빈 인터페이스(아직 미구현)
  cli.py             검색·마이그레이션 CLI 진입점
app/streamlit_app.py 검색 화면 + 게이트 B 판단 기록 폼
tests/               단위 테스트 + fixtures/(모두 샘플 데이터, 실제 KIPRIS 응답·판단 기록 아님)
```

## 판단 기록 (게이트 B)

판단은 `(출원번호, 검토 기술)` 키로 SQLite `judgment` 테이블에 append-only로 쌓인다(UPDATE/DELETE 경로 없음). 같은 키를 다시 판단하면 새 행이 `previous_judgment_id`로 이전 판단을 가리킨다. 저장 전 검증:

- **결정**: 신규 출원 검토 / 기존 IP 보강 검토 / 유지 / 정리 검토 / 타사 특허 확인 필요 중 하나
- **사유**: 공백 불가
- **전제**: 1개 이상 (출처·확인 키·기대값)
- **담당자**, **재검토 기한**: 필수

전제 재확인 시 IPC·출원인은 값의 순서와 무관하게 **집합 비교**로 판정한다(`ipauto.judgments.compare`).

## 점수는 법적 판단이 아니다

관련도 점수와 우선순위는 사람이 먼저 검토할 특허를 정렬하기 위한 보조 지표일 뿐이며, 선행특허 여부·등록 가능성·침해 여부에 대한 법적 판단이나 법률 자문이 아니다. 최종 IP 조치 판단은 항상 사람이 내린다.

## 알려진 한계

- 화면에 100점 만점 점수가 그대로 노출된다(3단계 구간만 표시하도록 바꾸는 것은 단계 2 남은 작업).
- 마이그레이션된 옛 판단 행은 검토 기술·검색어·담당자·재검토 기한이 실제 값이 아니라 "이전 데이터" 표시이며, 결정값도 원래의 관련도 판단이 아니라 사람 재확인을 유도하는 "타사 특허 확인 필요"로 일괄 표시된다(원래 판단은 `legacy_note`에 보존).
- 사건 감지·트리아지·판단 카드·전제 감시·Jira 연동은 아직 없다(단계 3~5).
