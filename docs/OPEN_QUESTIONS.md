# 확인이 필요한 외부 사실

docs/DESIGN.md·PIPELINE.md에서 "확인 후 결정"으로 남긴 항목을 추적한다. 코드에는 추측값을 박지 않고 설정으로 분리했다.

| 항목 | 상태 | 현재 코드의 처리 | 확인 방법 |
| --- | --- | --- | --- |
| KIPRIS Plus가 HTTPS를 지원하는가 | 미확인 | `KIPRIS_BASE_URL` 환경변수로 분리(`src/ipauto/config.py`). 기본값은 기존 http 엔드포인트. HTTPS 확인 전까지 접근키가 평문 전송된다는 위험이 있음 | KIPRIS Plus 문서 또는 고객센터에 HTTPS 엔드포인트 존재 여부 문의 |
| KIPRIS가 출원인 기준 조회를 지원하는가 | 미확인 | 자사 IP 포트폴리오 수집(단계 3 선행조건)에 필요. 현재는 `word` 자유검색만 구현 | KIPRIS Plus API 명세에서 출원인 전용 파라미터 확인 |
| IPC H01M 10/60~10/667이 배터리 열관리의 정확한 범위인가 | 미확인 | `config/ipc_rules.yaml`은 서브레인지가 아니라 `H01M`, `B60L` **패밀리 단위**만 인식(더 넓지만 더 안전한 신호) | 특허청 IPC 공식 분류표와 대조 후 `config/ipc_rules.yaml`에 반영 |
| KIPRIS `resultCode` 값의 의미(키 오류/쿼터 초과/기타)를 코드별로 구분할 수 있는가 | 미확인 | HTTP 상태(401/403→인증오류, 429→쿼터)만으로 예외를 구분하고, XML 레벨 실패(`successYN=N`)는 `resultMsg`를 그대로 사용자에게 보여줌(`KiprisResponseError`). resultCode 문자열을 추측해 분류하지 않음 | 실제 실패 응답 샘플(키 오류/쿼터 초과 각각)을 수집해 `resultCode` 매핑표 작성 |
| kiwipiepy가 이 환경의 Python 버전에서 설치되는가 | 확인됨 | Python 3.14.0에서 `pip install kiwipiepy`가 `cp39-abi3` 휠로 설치 가능함을 dry-run으로 확인(단계 2에서 실제 도입) | — |

## 별도 확인이 필요한 인프라 사항 (도메인 사실은 아님)

- 이 개발 환경에 `gh` CLI가 설치되어 있지 않아 `gh pr create`를 실행할 수 없다. PR 생성 방식은 사용자와 별도로 확인이 필요하다.
