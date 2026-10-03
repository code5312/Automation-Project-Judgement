# 사람 판단 중심 IP 업무 자동화

KIPRIS Plus의 실제 특허 데이터를 검색·점수화해 사람이 먼저 검토할 후보의 우선순위를 보여주고, 사람의 IP 조치 판단을 이유·전제와 함께 append-only로 기록하는 도구다. 가짜 특허 데이터를 생성하지 않으며, 최종 판단은 항상 사람이 한다. 전체 설계는 [docs/DESIGN.md](docs/DESIGN.md), 진행 단계는 [docs/PIPELINE.md](docs/PIPELINE.md), 확인이 필요한 외부 사실은 [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)를 참고한다.

이 저장소는 현재 **단계 1(데이터 모델)**, **단계 2(수집·순위)** 를 완료했다. 평가 세트(`data/eval/ev_battery_cooling_v1.json`, 실제 KIPRIS 데이터 40건)는 담당자 mingyu가 2026-10-02에 확정했고, 기준선 75.0% → 80.0%로 완료 기준을 충족했다(`data/eval/README.md`, docs/PIPELINE.md 평가 지표 기록). **단계 3(트리아지·카드)** 은 자사 IP 포트폴리오 적재(`data/portfolio/README.md`), GitHub 릴리스 → Event 입력 커넥터, 사건 ↔ IP 자산 Link 연결, LLM 구조화 분류 프롬프트, 애매 큐 라우팅 규칙, 자동 종결 로그·표본 감사 화면까지 진행했다.

## 설치와 실행

Python 3.12 이상이 필요하다.

```powershell
pip install -e ".[dev]"
$env:KIPRIS_ACCESS_KEY = "YOUR_ACCESS_KEY"
streamlit run app/streamlit_app.py
```

위 명령은 검색/게이트 B 화면과 함께 "자동 종결 표본 감사" 화면(`app/pages/sample_audit.py`)도 사이드바에 띄운다(Streamlit의 `pages/` 디렉터리 자동 인식).

처음 실행하거나 예전 `data/judgments.json` 판단 기록이 있다면, 실행 전에 SQLite로 1회 이관한다(재실행해도 중복 없이 안전하다):

```powershell
python -m ipauto.cli migrate-judgments
```

CLI로 직접 검색·CSV 저장을 하려면(검색어는 여러 개를 공백으로 구분해 전달할 수 있으며, 결과는 출원번호 기준으로 중복 제거된다):

```powershell
python -m ipauto.cli search "battery" "cooling" --technology "전기차 배터리 냉각" --debug
```

특정 출원번호를 다시 조회(전제 재확인/관심목록용)하려면:

```powershell
python -m ipauto.cli lookup "10-2020-1234567"
```

평가 세트 대비 현재 점수 로직의 정확도를 측정하려면(기본값은 `data/eval/ev_battery_cooling_v1.json`):

```powershell
python -m ipauto.cli evaluate
```

자사 IP 포트폴리오(KIPRIS 레코드 JSON 배열)를 `ip_asset`에 적재하려면:

```powershell
python -m ipauto.cli portfolio-load data/portfolio/demo_own_company_v1.json
```

공개 GitHub 레포의 릴리스를 "오픈소스 공개" 사건(Event)으로 가져오려면(접근키 불필요, 재실행해도 `(source, source_ref)` 기준으로 중복 안 쌓임):

```powershell
python -m ipauto.cli ingest-github-releases cli cli
```

사건 1건을 현재 IP 포트폴리오(자사·외부 구분 없이 전부)와 비교해 관련도 높은 자산에 Link를 제안하려면(기존 개념/IPC 스코어러 재사용, 재실행해도 중복 안 생김):

```powershell
python -m ipauto.cli link-event 1
python -m ipauto.cli confirm-link 1
```

사건 1건과 IP 자산 1건의 관련성을 LLM(Claude)에게 구조화 JSON(label·confidence·evidence·missing_info)으로 판단시키려면(`ANTHROPIC_API_KEY` 필요, 법률 자문이 아니며 최종 결정은 항상 사람이 함):

```powershell
$env:ANTHROPIC_API_KEY = "YOUR_API_KEY"
python -m ipauto.cli classify-link 1 1
```

사건 1건과 IP 자산 1건을 무관/관련/애매로 라우팅하려면(`ANTHROPIC_API_KEY`가 있으면 LLM 신호까지 함께 쓰고, 없으면 키워드/IPC 신호만으로 라우팅한다):

```powershell
python -m ipauto.cli triage 1 1
```

## 환경 변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `KIPRIS_ACCESS_KEY` | 필수 | KIPRIS Plus freeSearchInfo 접근키. 코드·로그·오류 메시지에는 절대 원문으로 남지 않는다(URL 인코딩된 형태까지 마스킹). |
| `KIPRIS_BASE_URL` | 선택 | KIPRIS 엔드포인트 재정의용. HTTPS 지원 여부가 아직 미확인이라 기본값은 http 엔드포인트다(docs/OPEN_QUESTIONS.md 참고). |
| `IPAUTO_DB_PATH` | 선택 | SQLite 파일 경로 재정의용. 기본값은 `data/ipauto.db`(커밋되지 않음). |
| `IPAUTO_CONFIG_DIR` | 선택 | 개념 그룹·가중치·IPC 규칙 YAML 디렉터리 재정의용. 기본값은 `config/`. |
| `ANTHROPIC_API_KEY` | `classify-link`에만 필수 | Claude API 키. 코드·로그·오류 메시지에는 원문으로 남지 않는다(마스킹). |

`.env.example`을 참고해 로컬 `.env` 파일을 만들 수 있으나, 이 프로젝트는 `.env` 파일을 자동 로드하지 않는다. 셸 환경변수로 직접 설정해야 한다.

## 디렉터리 구조

```
config/
  concepts.yaml      개념 그룹·가중치·보너스 설정
  ipc_rules.yaml      IPC 패밀리·개념-IPC 매핑 설정
data/eval/           평가 세트(JSON) + README.md(출처·라벨 검증 상태 설명)
data/portfolio/      자사 IP 포트폴리오 데모 데이터(JSON) + README.md(출처·가상 역할 설명)
src/ipauto/
  config.py          환경변수 로드, 키 마스킹
  connectors/kipris.py   KIPRIS 호출(fetch_all: 다중 검색어·페이지네이션, fetch_by_application_number: 재조회)·XML 파싱(defusedxml)·오류 분류
  connectors/github.py   공개 GitHub releases API 호출(인증 불필요)
  connectors/llm.py   Anthropic Messages API 호출(urllib 직접 호출, SDK 미사용)
  scoring/           ipc.py(패밀리+주 신호), keywords.py(kiwipiepy 형태소 분석), bands.py — 관련도 점수·구간, rules.py — config/*.yaml 로더
  evaluation.py      평가 세트 로드·정확도/혼동행렬 측정
  portfolio.py       자사/외부 IP 포트폴리오 적재 (IPAsset)
  events.py          사건 정규화·적재 (Event; 현재는 GitHub 릴리스 → "오픈소스 공개")
  linking.py         사건 ↔ IP 자산 Link 제안 (기존 점수 로직 재사용)
  triage/llm_classifier.py   LLM 구조화 판정(few-shot + JSON 형식 검증)
  triage/routing.py   무관/관련/애매 라우팅(애매 큐 규칙 5가지)
  db/                schema.sql, connection.py, repositories.py — SQLite 저장소(Judgment·Premise·IPAsset·Event·Link·AutoCloseLog 등)
  judgments/         service.py(게이트 B 검증), compare.py(집합 비교), migrate_json.py
  triage/ cards/ watch/   단계 3·4용 빈 인터페이스(llm_classifier·routing 제외 아직 미구현)
  cli.py             검색·재조회·평가·포트폴리오 적재·사건 수집·Link 제안/확인·LLM 분류·트리아지·마이그레이션 CLI 진입점
app/streamlit_app.py 검색 화면 + 게이트 B 판단 기록 폼
app/pages/sample_audit.py   자동 종결 표본 감사 화면
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

- 마이그레이션된 옛 판단 행은 검토 기술·검색어·담당자·재검토 기한이 실제 값이 아니라 "이전 데이터" 표시이며, 결정값도 원래의 관련도 판단이 아니라 사람 재확인을 유도하는 "타사 특허 확인 필요"로 일괄 표시된다(원래 판단은 `legacy_note`에 보존).
- `ipauto.cli lookup`/`fetch_by_application_number`는 출원번호 전용 조회 API가 아니라 자유검색(`word`)에 출원번호를 그대로 넣어 재조회한다. KIPRIS가 출원번호를 자유검색 색인에 포함하는지 확인되지 않아, 결과가 없다고 해서 출원이 존재하지 않는다고 단정할 수 없다(docs/OPEN_QUESTIONS.md).
- 평가 세트가 40건·한 기술 분야("전기차 배터리 냉각")뿐이라 개념/범용 임계값(현재 둘 다 70/40)과 주 IPC 신호 보너스(15점) 등은 폭넓게 검증된 값이 아니다. 확정된 평가 세트 기준 정확도는 80.0%(32/40, `docs/PIPELINE.md` 평가 지표 기록)이며, 차량+배터리 텍스트만으로 "보통" 밴드에 걸치는 경계 사례나 "냉각수 히팅파이프"처럼 냉각이 아닌 가열 기능을 가진 부품을 구분하는 문제가 남아 있다. 이런 의미 이해가 필요한 사례는 향후 LLM 분류(단계 3)로 보강하는 쪽을 검토한다.
- 자사 IP 포트폴리오 적재(`ip_asset`), GitHub 릴리스 사건 수집(`event`), 사건↔IP 자산 Link 제안, LLM 구조화 분류(`classify-link`), 무관/관련/애매 라우팅(`triage`), 자동 종결 로그·표본 감사 화면까지는 됐지만, 게이트 A 화면·판단 카드·전제 감시·Jira 연동은 아직 없다(단계 3 나머지~5).
- `ipauto.db.connection.connect`가 `check_same_thread=False`로 열려 있어 캐싱된 커넥션을 여러 스레드에서 재사용할 수 있지만, 이건 Streamlit이 한 세션 안에서는 재실행을 순차적으로 실행한다는 가정에 의존한다. 실제 동시 다중 사용자 쓰기에 안전한지는 아직 검증되지 않았고, "저장소: SQLite로 충분한지, 동시 사용자 수"는 여전히 docs/PIPELINE.md 블로커 표의 미결정 사항이다.
- `ipauto.triage.routing`의 "신호 불일치" 규칙은 docs/DESIGN.md가 원래 말하는 "임베딩 유사도 vs LLM" 조합이 아니라, 이 저장소에 실제로 있는 "키워드/IPC 점수 밴드 vs LLM" 조합이다. 임베딩 유사도 신호는 아직 구현되지 않았다.
- `classify-link`는 이 개발 환경에 `ANTHROPIC_API_KEY`가 없어 실제 Claude 호출로 끝까지 검증하지 못했다. 연결(`connectors/llm.py`)과 응답 파싱·형식 검증(`triage/llm_classifier.py`)은 모킹 테스트로만 확인했으니, 실제 키가 있는 환경에서 한 번 실행해 확인해야 한다.
- GitHub 커넥터는 공개 릴리스 목록을 주기적으로 다시 불러오는(폴링) 방식이다. 웹훅 수신은 아직 없고, 비공개 레포·인증이 필요한 호출(레이트 리밋 상향 등)도 지원하지 않는다.
- `ipauto.linking`은 기존 개념/키워드/IPC 스코어러로 "낮음" 밴드 이상만 Link를 제안한다. 제목만 있고 초록이 없는 포트폴리오 항목(예: `data/portfolio/demo_own_company_v1.json`)은 제목에 등장하는 개념 키워드가 적어 구조적으로 낮은 점수에 머물 수 있다 — 실제로 "배터리 팩" 항목은 어떤 사건 문구를 넣어도 "낮음"을 못 벗어나는 것을 확인함. 초록까지 채우면 개선된다.
