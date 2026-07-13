# 스프린트 1 — 기능 3: BP 리서치 엔진

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4절 ResearchContext 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 3 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.3.

- 최종 수정일: 2026-07-13
- 상태: 계약 v0.4 반영 (검색 백엔드 = 다중 소스 실시간 API(논문 API), LLM 옵션화, seed 병합. 구현 완료)

---

## 1. 이 기능이 하는 일 (계약 요약)

- **입력**: 목표 정의서 `GoalDefinition` (goal_text + org_constraints + candidate_tasks) — 계약 1절
- **하는 일**: 목표 텍스트 + 조직 제약을 바탕으로 논문/연구 등을 실시간 외부 API로 조회 → 요약·구조화(+큐레이션 seed 병합). **RAG의 "R"만 담당.**
- **하지 않는 일**: 로드맵/task 생성, 적합성 판정, 사용자에게 결과 직접 노출 (전부 4번의 역할)
- **출력**: `ResearchContext` — 계약 4절 스키마. 코드 경계는 `run_research(goal: GoalDefinition) -> ResearchContext` 함수 하나 (계약 2.3절)

## 2. 확정 사항

- [x] ~~웹서치 구현 방식: Gemini API + Google Search grounding~~ → **v0.4에서 변경**: Gemini grounding은 무료 API 티어에서 사용 불가(404/429, grounding 유료 게이팅)로 확인 → **다중 소스 실시간 API**로 교체. **스프린트1 범위: Semantic Scholar + arXiv**(논문 API, 완전 무료·안정). `source_url`·발행일은 API 응답에서 직접 추출 (계약 v0.4 §2.5)
- [x] ~~요약 생성 모델: Gemini API~~ → **v0.4에서 옵션화**: 소스 API가 abstract를 구조화 제공하므로 LLM 불필요. 핵심 경로는 LLM 없이 동작(요약=abstract 트림), Gemini 요약은 정상 키 확보 시 품질 향상 옵션(실패 시 트림으로 degrade). `GEMINI_API_KEY_RESEARCH`는 옵션
- [x] 큐레이션 seed findings 병합: 웹/검색에 없는 소수 근거(사내 리포트 등)를 `Finding`으로 정리해 병합(주 메커니즘은 실시간, 별도 wiki 미구축 — 계약 v0.4 §2.6)
- [x] 통합 형태: 같은 repo `research/` 패키지, 별도 서비스 아님
- [x] 실패 계약: 검색 실패 시 예외 대신 `status="failed"` + 빈 `findings` 반환 (계약 4절)
- [x] 픽스처 책임: `fixtures/research_context_goal_001.json` 작성은 3번 담당자, 검수는 4번 담당자 (계약 7절)

## 3. 담당자 확인·결정 사항 (남은 체크리스트)

- [x] `ResearchContext` 스키마 최종 검토 — 계약 §4 그대로 `app/contracts/research.py`(`ResearchContext`/`Finding`)로 코드화. 변경 없음(8절 절차 불필요)
- [x] 리서치 실행 시점: **실시간 웹서치 유지 + 동일 `goal_id` 재요청은 캐싱** (계약 v0.3 2.4절 확정). 캐시 키=`goal_id`, `status="failed"`는 캐싱하지 않음. 저장 방식은 담당자 재량(§4-6)
- [x] 소스 신뢰도 기준: 스프린트1은 경량 필터 — grounding metadata의 **실제 http(s) URL을 가진 소스만** 통과 + URL 중복 제거(`app/research/filters.py`). 도메인 블록리스트 등 고도화는 오픈 이슈로 유지
- [x] `metric_snippet` 수치 검증: (1) 구조화 프롬프트에서 "출처가 분명한 수치만, 없으면 null, 지어내지 말 것" 강제 + (2) 코드에서 **숫자가 없는 문자열은 metric으로 인정하지 않고 null 처리**(`sanitize_metric`). grounding 인용 구간 정밀 대조는 오픈 이슈
- [x] `source_type` 분류: 구조화 단계에서 모델이 `trend`(트렌드/일반) / `research`(논문·연구·리포트) / `practice`(개인·현장 활용법)로 분류, `Literal`로 스키마 강제
- [x] `partial` 판정 기준: findings **0건→failed, 1~2건→partial, 3건 이상→ok** (`OK_THRESHOLD=3`, 계약 §4 "목표 3~8건" 기준)

## 4. 구현 결과 (완료)

디렉토리 소유: `app/research/` (기능 3 전용), 스키마는 `app/contracts/` (공동). 진입점은 `run_research(goal) -> ResearchContext` 하나.

| 파일 | 역할 |
|---|---|
| `app/research/service.py` | `run_research()` 진입점. 캐시조회→쿼리빌드→소스 어댑터 실시간 조회→seed 병합→필터·중복제거→status판정→캐시저장. **실패 계약**(예외 미전파, failed+빈 findings)을 여기서 보장 |
| `app/research/query_builder.py` | `goal_text`+`org_constraints`로 검색 쿼리 2~4개 생성(도구·연동 시스템 + AX 키워드). 추후 LLM 키워드 추출로 승격 가능 |
| `app/research/sources/` | 소스 어댑터. `semantic_scholar.py`·`arxiv.py` — 요청 시점 실시간 HTTP 조회로 논문 title/abstract/url/연도 수집(키 불필요). 어댑터별 예외는 상위에서 흡수 |
| `app/research/seed.py` | 큐레이션 seed findings 로더(`fixtures/seed_findings_*.json`). 실시간 결과와 같은 스키마로 병합 (계약 §2.6) |
| `app/research/filters.py` | 소스 신뢰도 필터(http url) + metric 수치 검증(`sanitize_metric`) + abstract 요약 트림 |
| `app/research/cache.py` | `goal_id → ResearchContext` 인메모리 캐시 (계약 §2.4) |

- **LLM 불필요**: 소스 API가 구조화 데이터를 주므로 핵심 경로에 Gemini 호출이 없다 → 무료 티어 쿼터 문제와 무관. (Gemini grounding 기반 이전 구현은 v0.4에서 제거)
- **요약**: `summary`는 abstract를 2~3문장으로 트림(스프린트1). "원문 그대로 X"(SPEC 4.3) 완전 충족은 LLM 요약이 필요 → 정상 키 확보 시 옵션으로 추가(오픈 이슈).
- **published_date**: 이제 API가 발행연도를 주므로 채워진다(이전 grounding에선 null).
- **테스트**: `tests/test_contracts.py` — 스키마 검증 + `failed` 경로 + 캐싱 + seed 병합 + 중복제거. 네트워크 미사용(소스 어댑터 monkeypatch). 실제 API 스모크는 `scripts/smoke_research.py`(수동, **무료 API라 상시 실행 가능**).

### ✅ 스모크 테스트 상태

- **v0.4 전환 후 실제 API 스모크 통과 대상**: Semantic Scholar/arXiv는 무료·키불필요라 `run_research(goal_001)`을 실제로 호출해 `ok`/`partial` 결과를 받을 수 있다. (이전 Gemini grounding 구현은 무료 키에서 404/429로 성공 스모크가 막혔었음 — 그 문제가 이번 전환으로 해소)
- 실패 계약은 어댑터가 모두 실패하는 경우로 검증(네트워크 차단/타임아웃 시 `failed`).

## 5. 오픈 이슈

- ~~리서치 갱신 주기~~ → 계약 v0.3 §2.4 확정: `goal_id` 단위 캐싱, 갱신 주기 자동화는 이후 스프린트
- LLM 요약 품질(현재 abstract 트림) — 정상 Gemini 키/유료 티어 확보 시 요약 단계 옵션 추가
- 소스 확장: GitHub(`practice`)·범용 검색(`trend`) 어댑터 추가(계약 §2.5 이후 확장)
- 한글 목표 → 영문 논문 API 쿼리 키워드 품질(현재 도구·시스템·AX 키워드 조합, LLM 키워드 추출로 승격 가능)

## 6. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-13 | v0.4 pivot — Gemini grounding 무료 티어 불가(404/429) 확인 → 검색 백엔드를 **다중 소스 실시간 API(Semantic Scholar + arXiv)**로 교체, LLM 요약 옵션화(핵심 경로 LLM 불필요), 큐레이션 seed findings 병합 추가. `gemini_client.py` 제거, `research/sources/`·`seed.py` 신설. 스키마·시그니처 불변 |
| 2026-07-13 | 기능 3 구현 완료 — `contracts/goal.py`·`research.py`, `fixtures/goal_001.json`·`research_context_goal_001.json`, `research/`(service·query_builder·gemini_client·filters·cache), `tests/test_contracts.py`(20 passed), `scripts/smoke_research.py`. 3절 체크리스트 전부 확정. 실제 API 실패 계약 검증됨, ok 스모크는 계정 쿼터 이슈로 보류(§4) |
| 2026-07-13 | 계약 v0.3 반영 — 리서치 캐싱 정책 확정(실시간 웹서치 + `goal_id` 단위 캐싱, `status="failed"` 미캐싱). 3절 캐싱 체크리스트 확정 처리, 5절 오픈 이슈에서 갱신 주기 이슈 종료 |
| 2026-07-11 | 계약 v0.2 반영 — 웹서치 방식(Gemini grounding)·통합 형태(모듈)·실패 계약 확정, 구현 계획 골격 추가 |
