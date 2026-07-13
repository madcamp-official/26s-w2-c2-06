# 스프린트 1 — 기능 3: BP 리서치 엔진

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4절 ResearchContext 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 3 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.3.

- 최종 수정일: 2026-07-13
- 상태: 계약 v0.3 반영 (리서치 캐싱 정책 확정. 구현 계획 골격 확정, 세부는 담당자가 채움)

---

## 1. 이 기능이 하는 일 (계약 요약)

- **입력**: 목표 정의서 `GoalDefinition` (goal_text + org_constraints + candidate_tasks) — 계약 1절
- **하는 일**: 목표 텍스트 + 조직 제약을 바탕으로 AX 트렌드/논문/frontier 개인 AI 활용법을 웹서치 → 요약·구조화. **RAG의 "R"만 담당.**
- **하지 않는 일**: 로드맵/task 생성, 적합성 판정, 사용자에게 결과 직접 노출 (전부 4번의 역할)
- **출력**: `ResearchContext` — 계약 4절 스키마. 코드 경계는 `run_research(goal: GoalDefinition) -> ResearchContext` 함수 하나 (계약 2.3절)

## 2. 확정 사항 (계약 v0.2에서 결정됨)

- [x] 웹서치 구현 방식: **Gemini API + Google Search grounding** — 별도 검색 API 없이 검색+요약을 한 호출로. `source_url`은 grounding metadata에서 추출
- [x] 요약 생성 모델: **Gemini API** (무료 티어 우선)
- [x] 통합 형태: 같은 repo `research/` 패키지, 별도 서비스 아님
- [x] 실패 계약: 검색 실패 시 예외 대신 `status="failed"` + 빈 `findings` 반환 (계약 4절)
- [x] 픽스처 책임: `fixtures/research_context_goal_001.json` 작성은 3번 담당자, 검수는 4번 담당자 (계약 7절) — **스프린트 첫 작업으로 우선 처리**

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
| `app/research/service.py` | `run_research()` 진입점. 캐시조회→쿼리빌드→(관점별)검색+구조화→필터·중복제거→status판정→캐시저장. **실패 계약**(예외 미전파, failed+빈 findings)을 여기서 보장 |
| `app/research/query_builder.py` | `goal_text`+`org_constraints`로 검색 관점 2~4개 생성(템플릿 기반: 도구 특화/방법론·연구/실패 요인/연동 시스템). 추후 LLM 쿼리 생성으로 승격 가능 |
| `app/research/gemini_client.py` | `grounded_search()`(google_search grounding→텍스트+실제 소스 추출) / `structure_findings()`(response_schema로 findings JSON 강제, 도구 없음). **URL/제목은 모델이 만들지 않고 grounding 실제 소스에서 매핑** |
| `app/research/filters.py` | 소스 신뢰도 필터 + metric 수치 검증(`sanitize_metric`) |
| `app/research/cache.py` | `goal_id → ResearchContext` 인메모리 캐시 (계약 §2.4) |

- **모델**: `settings.gemini_research_model`(env `GEMINI_RESEARCH_MODEL`, 기본 `gemini-flash-latest`). 계정/티어별 사용 가능 모델 차이 대응 — 코드 수정 없이 env로 교체.
- **2단계 호출 이유**: Gemini는 grounding 도구와 structured output(responseSchema)을 한 호출에 함께 쓰기 어렵다. 그래서 ① 그라운딩 검색 → ② 무도구 구조화 2호출로 분리(관점당 2호출).
- **테스트**: `tests/test_contracts.py` — 스키마 검증 + `failed` 경로 + 캐싱 + 방어(범위 밖 인덱스/수치 없는 metric). 네트워크 미사용(Gemini 호출부 monkeypatch). 실제 API 스모크는 `scripts/smoke_research.py`(수동).

### ⚠️ 스모크 테스트 상태 (실제 API)

- **실패 계약은 실제 API로 검증됨**: 발급 키가 신규 계정 제약으로 `gemini-2.5-*` 계열은 404, 그 외 모델은 429(RESOURCE_EXHAUSTED, 계정 쿼터 소진 상태) — 이 에러들이 모두 `status="failed"`+빈 findings로 안전하게 처리됨(예외 미전파). 스키마 라운드트립도 통과.
- **성공(ok) 스모크는 보류**: 현재 발급 키가 plain 호출조차 429라 근거가 있는 `ok` 결과를 실제로 받지 못했다. 이는 코드 문제가 아니라 **계정 쿼터/모델 접근 이슈**다. 키 쿼터 회복 또는 grounding 가능한 모델 확보(필요 시 billing) 후 `uv run python scripts/smoke_research.py`로 재확인 예정. 자세한 확인 절차는 `docs/setup/API_KEY_SETUP.md §5`.

## 5. 오픈 이슈 (SPEC.md 4.3에서 이관)

- ~~리서치 갱신 주기 (캐싱 정책과 함께 결정)~~ → 계약 v0.3 2.4절에서 확정: 실시간 웹서치 + `goal_id` 단위 캐싱(스프린트1은 갱신 주기 없이 1회 조사 후 재사용). 갱신 주기 자동화는 이후 스프린트로 이관
- 소스 신뢰도 기준
- 캐시 저장 방식: 스프린트1은 프로세스 인메모리 캐시(`goal_id → ResearchContext`)로 시작, 필요 시 이후 파일/DB로 승격 (구현 시 확정)

## 6. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-13 | 기능 3 구현 완료 — `contracts/goal.py`·`research.py`, `fixtures/goal_001.json`·`research_context_goal_001.json`, `research/`(service·query_builder·gemini_client·filters·cache), `tests/test_contracts.py`(20 passed), `scripts/smoke_research.py`. 3절 체크리스트 전부 확정. 실제 API 실패 계약 검증됨, ok 스모크는 계정 쿼터 이슈로 보류(§4) |
| 2026-07-13 | 계약 v0.3 반영 — 리서치 캐싱 정책 확정(실시간 웹서치 + `goal_id` 단위 캐싱, `status="failed"` 미캐싱). 3절 캐싱 체크리스트 확정 처리, 5절 오픈 이슈에서 갱신 주기 이슈 종료 |
| 2026-07-11 | 계약 v0.2 반영 — 웹서치 방식(Gemini grounding)·통합 형태(모듈)·실패 계약 확정, 구현 계획 골격 추가 |
