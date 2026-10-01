# 확인이 필요한 외부 사실

docs/DESIGN.md·PIPELINE.md에서 "확인 후 결정"으로 남긴 항목을 추적한다. 코드에는 추측값을 박지 않고 설정으로 분리했다.

| 항목 | 상태 | 현재 코드의 처리 | 확인 방법 |
| --- | --- | --- | --- |
| KIPRIS Plus가 HTTPS를 지원하는가 | 미확인 | `KIPRIS_BASE_URL` 환경변수로 분리(`src/ipauto/config.py`). 기본값은 기존 http 엔드포인트. HTTPS 확인 전까지 접근키가 평문 전송된다는 위험이 있음 | KIPRIS Plus 문서 또는 고객센터에 HTTPS 엔드포인트 존재 여부 문의 |
| KIPRIS가 출원인 기준 조회를 지원하는가 | 미확인 | 자사 IP 포트폴리오 수집(단계 3 선행조건)에 필요. 현재는 `word` 자유검색만 구현 | KIPRIS Plus API 명세에서 출원인 전용 파라미터 확인 |
| IPC H01M 10/60~10/667이 배터리 열관리의 정확한 범위인가 | 확인됨 (2026-10-01) | WIPO IPC 2026.01 scheme과 USPTO CPC definition(H01M10/60="Heating or cooling; Temperature control", H01M10/613="Cooling or keeping cold", H01M10/625="Vehicles", ..., H01M10/667이 마지막이고 다음은 H01M12/00)으로 교차 확인. `config/ipc_rules.yaml`의 `primary_signals`에 주 신호(정밀 서브그룹 범위)로 반영했고, `H01M`/`B60L` 패밀리 단위 신호는 보조 신호로 계속 사용 | [WIPO IPC H01M scheme](https://www.wipo.int/ipc/itos4ipc/ITSupport_and_download_area/20260101/pdf/scheme/full_ipc/en/h01m.pdf), [USPTO CPC H01M scheme](https://www.uspto.gov/web/patents/classification/cpc/html/cpc-H01M.html) |
| KIPRIS `resultCode` 값의 의미(키 오류/쿼터 초과/기타)를 코드별로 구분할 수 있는가 | 미확인 | HTTP 상태(401/403→인증오류, 429→쿼터)만으로 예외를 구분하고, XML 레벨 실패(`successYN=N`)는 `resultMsg`를 그대로 사용자에게 보여줌(`KiprisResponseError`). resultCode 문자열을 추측해 분류하지 않음 | 실제 실패 응답 샘플(키 오류/쿼터 초과 각각)을 수집해 `resultCode` 매핑표 작성 |
| kiwipiepy가 이 환경의 Python 버전에서 설치되는가 | 확인됨 | Python 3.14.0에서 `pip install kiwipiepy`로 실제 설치·사용 중(`kiwipiepy==0.24.0`, `src/ipauto/scoring/keywords.py`의 `extract_generic_keywords`). `pyproject.toml` 의존성에 반영 | — |
| KIPRIS가 출원번호 전용 조회 파라미터/엔드포인트를 지원하는가 | 미확인 | `fetch_by_application_number`(`src/ipauto/connectors/kipris.py`)는 전용 파라미터 없이 출원번호를 `word` 자유검색에 그대로 넣어 재조회하고, 반환된 레코드 중 출원번호가 정확히 일치하는 것만 고른다. 매칭 실패가 "출원 없음"을 뜻하지 않음을 docstring·CLI 메시지에 명시 | KIPRIS Plus API 명세에서 출원번호 전용 파라미터 확인 |

## 별도 확인이 필요한 인프라 사항 (도메인 사실은 아님)

- 이 개발 환경에 `gh` CLI가 설치되어 있지 않아 `gh pr create`를 실행할 수 없다. PR 생성 방식은 사용자와 별도로 확인이 필요하다.
