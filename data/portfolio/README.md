# IP 포트폴리오 데모 데이터 (docs/PIPELINE.md 단계 3)

## `demo_own_company_v1.json`

단계 3 선행 블로커 "데모 데이터" 결정(docs/PIPELINE.md 블로커 표, 2026-10-02, **가상 회사·가상 출원 목록**)에 따른 데모용 "자사 IP 포트폴리오"다.

- **특허 데이터 자체는 실제 KIPRIS 공개 데이터다.** `outputs/kipris_patents_*.csv`(2026-09-28, 실제 KIPRIS Plus 호출 결과)에서 주식회사 엘지에너지솔루션 명의의 실제 출원 3건을 골랐다. 가짜 특허 데이터를 생성하지 않는다는 원칙(`README.md`)을 지켰다.
- **"자사"라는 역할만 가상이다.** 이 저장소는 엘지에너지솔루션과 아무 관계가 없다 — 임의의 실제 공개 특허를 데모 워크스루용 "우리 회사 포트폴리오" 역할로 가정해 사용했을 뿐이며, 실제 고객·제휴 관계를 나타내지 않는다.
- `python -m ipauto.cli portfolio-load data/portfolio/demo_own_company_v1.json`으로 `ip_asset` 테이블(`asset_kind='자사'`)에 적재한다(`src/ipauto/portfolio.py`). 재실행해도 출원번호 기준 upsert라 중복되지 않는다.

### 실제 회사로 바꾸려면

KIPRIS가 출원인 기준 조회를 지원하는지 아직 미확인이라(`docs/OPEN_QUESTIONS.md`), 지금은 출원번호를 직접 알아야 적재할 수 있다. 실제 접근키가 있다면 `ipauto.portfolio.ingest_application_numbers(conn, 출원번호_목록, access_key)`로 KIPRIS를 재조회해 최신 상태로 적재할 수 있다.
