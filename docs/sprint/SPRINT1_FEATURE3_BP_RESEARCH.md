# 스프린트 1 — 기능 3: BP 리서치 엔진

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4절 ResearchContext 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 3 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.3.

- 최종 수정일: 2026-07-13
- 상태: 계약 v0.7 반영 (소스 4종: 논문 API + GitHub + Tavily, Reddit 기각. AX 리포트 6건 기반 seed 14건. 기능 4와 병합 통합 완료. §2.4 HTTP 오케스트레이션 계약 불일치 해소. §2.9 소스 선택 로직을 pillar 라운드로빈으로 교체)

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
| `app/research/service.py` | `run_research()` 진입점. 캐시조회→쿼리빌드→seed 병합→**pillar 라운드로빈으로 소스 어댑터 실시간 조회**(§2.9)→필터·중복제거→status판정→캐시저장. **실패 계약**(예외 미전파, failed+빈 findings)을 여기서 보장 |
| `app/research/query_builder.py` | `goal_text`+`org_constraints`로 검색 쿼리 2~4개 생성(도구·연동 시스템 + AX 키워드). 추후 LLM 키워드 추출로 승격 가능 |
| `app/research/sources/` | 소스 어댑터 4종(§2.7). `semantic_scholar.py`·`arxiv.py`(논문, 키불필요) · `github.py`(practice, 키불필요·토큰있으면상향) · `tavily.py`(trend, 키 옵션·없으면 조용히 생략). 어댑터별 예외는 상위에서 흡수 |
| `app/research/seed.py` | 큐레이션 seed findings 로더(`fixtures/seed_findings_*.json`). 실시간 결과와 같은 스키마로 병합, `service.SEED_LIMIT`(=4)만큼만 요청당 사용 (계약 §2.6, §2.8) |
| `app/research/filters.py` | 소스 신뢰도 필터(http url) + metric 수치 검증(`sanitize_metric`) + abstract 요약 트림 |
| `app/research/cache.py` | `goal_id → ResearchContext` 인메모리 캐시 (계약 §2.4) |

- **LLM 불필요**: 소스 API가 구조화 데이터를 주므로 핵심 경로에 Gemini 호출이 없다 → 무료 티어 쿼터 문제와 무관. (Gemini grounding 기반 이전 구현은 v0.4에서 제거)
- **요약**: `summary`는 abstract를 2~3문장으로 트림(스프린트1). "원문 그대로 X"(SPEC 4.3) 완전 충족은 LLM 요약이 필요 → 정상 키 확보 시 옵션으로 추가(오픈 이슈).
- **published_date**: 이제 API가 발행연도를 주므로 채워진다(이전 grounding에선 null).
- **테스트**: `tests/test_research.py` — `run_research()` 동작(스키마·failed·캐싱·seed 병합·중복제거) 전담. 네트워크 미사용(소스 어댑터 4종 전부 monkeypatch). `tests/test_contracts.py`(기능 4 소유)는 공동 스키마/픽스처 검증만 담당 — origin/main 병합 후 역할 분리. 실제 API 스모크는 `scripts/smoke_research.py`(수동, **무료 API라 상시 실행 가능**).
- **seed 소스**: 사용자가 제공한 AX 리포트 6건(뤼튼·SK-AX×3·원티드·kt cloud)을 서브에이전트가 SPEC 기획 의도에 맞춰 분석해 `fixtures/seed_findings_goal_001.json`에 14건으로 큐레이션(§2.8). 요청당 `SEED_LIMIT=4`건만 병합되고 나머지는 실시간 조회로 채워진다.

### ✅ 스모크 테스트 상태

- **v0.4 전환 후 실제 API 스모크 통과**: Semantic Scholar/arXiv/GitHub는 무료·키불필요라 `run_research(goal_001)`을 실제로 호출해 `ok` 결과를 받을 수 있다. (이전 Gemini grounding 구현은 무료 키에서 404/429로 성공 스모크가 막혔었음 — 이번 전환으로 해소)
- GitHub Search 실 호출 검증: goal_001 관련 쿼리(`Copilot enterprise adoption` 등)에서 목표와 직접 연관된 저장소가 실제로 조회됨(예: Copilot 프롬프트 라이브러리).
- Tavily는 `TAVILY_API_KEY` 미설정 상태로 개발 — 호출 없이 빈 리스트를 반환하는 graceful degrade만 검증됨. 실제 trend 결과 스모크는 키 확보 후 재확인 필요(오픈 이슈).
- 실패 계약은 어댑터가 모두 실패하는 경우로 검증(네트워크 차단/타임아웃 시 `failed`).

### ✅ 기능 3↔4 통합 테스트 (계약 §7-4 DoD)

실제 `run_research(goal_001)` → `generate_roadmap()` 순차 호출을 코드 수정 없이 실행:

- **status=ok 경로**: `run_research(goal_001)` 실 호출(seed 4 + 실시간 4 = findings 8, status=ok) → `generate_roadmap(goal, research, onboarding)`에 그대로 투입 → 유효한 `RoadmapResult` 생성(라운드트립 스키마 검증 통과). 생성된 task가 seed findings(`F1`, `F3`)를 `source_refs`로 실제 인용함 — 3→4 근거 인용 경로가 실제로 동작.
- **status=failed 경로**: `ResearchContext(status="failed", findings=[])`를 수동 구성해 `generate_roadmap()`에 투입 → 정상적으로 `RoadmapResult` 생성, `research_status`가 `failed`로 정확히 echo되고 모든 task의 `source_refs`가 빈 배열(외부 근거 인용 없음, 계약 §4 "4번은 partial/failed에서도 동작" 요건 충족).
- **DoD 결론**: 계약 §7-4 통합 완료 기준 충족 — `run_research()` 출력을 `generate_roadmap()`에 코드 수정 없이 넣었을 때 유효한 결과가 나오고, `failed` 경로도 1회 검증됨.

### ✅ 해결됨 — HTTP 오케스트레이션 계약 불일치 (v0.6, 2026-07-13)

통합 테스트 중 `app/routers/roadmap.py`(기능 4 소유)가 계약 §2.4와 다르게 구현된 것을 발견했었다(과거 기록은 아래 참고). 사용자에게 비용-편익 분석 결과를 보고한 뒤, 사용자 승인 하에 라우터를 계약대로 수정했다.

**비용-편익 분석 요약**
- **Gemini 토큰 절감**: `generate_roadmap()`엔 캐싱이 없다. `goal_id`만으로 캐싱하면, 클라이언트가 매번 다른 `ResearchContext`를 보낼 수 있는 구조에서는 stale 응답 위험이 있어 안전하게 캐싱할 수 없다. 서버가 `run_research(goal)`을 직접 호출하면 `goal_id → research`가 결정적으로 고정되어, 그 위에 `RoadmapResult` 캐싱을 안전하게 얹을 수 있는 전제가 마련된다(캐싱 자체는 이번엔 미구현, 아래 "오픈 제안" 참고).
- **수정 범위**: `app/routers/roadmap.py` 한 파일. 스키마(`GoalDefinition`/`OnboardingData`/`RoadmapResult`) 변경 없음.
- **SPEC 가중치**: SPEC 4.3 "사용자 노출 여부: 없음"은 명시적으로 합의된 정책이며, 기존 구현은 단순 비효율이 아니라 정책 위반이었다.
- **결론**: 계약대로 라우터를 고치는 쪽으로 결정(계약을 코드에 맞추는 대안은 SPEC 위반을 정당화할 근거가 없어 기각).

**적용된 수정**
- `app/routers/roadmap.py`: `GenerateRoadmapRequest`에서 `research: ResearchContext` 필드 제거(`goal`+`onboarding`만). `/generate`·`/generate-and-publish` 핸들러가 내부에서 `run_research(payload.goal)`을 호출한 뒤 `generate_roadmap()`/`publish_roadmap()`에 넘긴다.
- `/publish`(독립 재발행 엔드포인트)도 동일하게 `PublishRoadmapRequest.research` 필드를 제거하고, 요청에 이미 있는 `goal`로 `run_research()`를 호출해 인용용 `ResearchContext`를 재구성한다 — `goal_id` 캐시 덕분에 `/generate`가 먼저 호출된 경우 즉시 캐시 히트.
- `app/notion/publish.py`의 `publish_roadmap()` 함수 시그니처(기능 4 소유)는 변경하지 않았다. 라우터가 넘기는 인자 값만 클라이언트 입력 대신 서버 계산값으로 바꿨다.
- `tests/test_roadmap_router.py`: `run_research`를 monkeypatch해 세 엔드포인트 모두 요청 바디에 `research`가 없어도 200 OK + 내부적으로 `run_research()`가 호출됨을 검증하도록 갱신. `generate-and-publish`는 `run_research()`가 정확히 1회만 호출되고 그 결과가 `generate_roadmap()`·`publish_roadmap()` 양쪽에 동일하게 전달됨을 검증하는 테스트를 신규 추가.
- **재검증**: (1) 함수 레벨 — 실제 `run_research(goal_001)` → `generate_roadmap()` 재실행, ok/failed 경로 및 `goal_id` 캐시 재사용 확인. (2) HTTP 레벨 — `TestClient`로 `/roadmap/generate`에 `goal`+`onboarding`만 전송 → 200 OK + `research/cache.py`의 `goal_id` 캐시에 값이 채워짐을 확인(=`run_research()`가 서버 내부에서 실제로 호출됨). `uv run pytest -q` 63 tests passed.
- **오픈 제안(미구현)**: `RoadmapResult`를 `goal_id` 단위로 캐싱하면 동일 목표 재요청 시 Gemini 호출(Stage A+B) 자체를 스킵할 수 있다. `app/roadmap/`은 기능 4 소유라 이번엔 라우터 수정만 반영했고, 캐싱 설계(위치·저장 방식)는 기능 4 담당자와 조율 필요 — §8 절차로 제안만 남긴다.

<details>
<summary>과거 기록 (해결 전, 참고용)</summary>

통합 테스트 중 `app/routers/roadmap.py`(기능 4 소유)가 계약 §2.4와 다르게 구현된 것을 발견했다:

- **계약 §2.4(확정)**: `POST /roadmap/generate`는 목표 정의서만 받고, 내부에서 `run_research()` → `generate_roadmap()`을 순차 호출한다. `ResearchContext`를 요청 바디로 받지 않는다(SPEC 4.3 리서치 레이어 비노출 정책).
- **실제 구현**: `GenerateRoadmapRequest`가 `research: ResearchContext`를 필수 필드로 요구하고, 핸들러는 `run_research()`를 호출하지 않은 채 요청 바디의 값을 그대로 `generate_roadmap()`에 전달한다(`generate-and-publish`도 동일).
- **영향**: (1) API 클라이언트가 `ResearchContext`(내부 검색 쿼리·근거 구조)를 직접 조립해서 보내야 함 — 리서치 레이어 비노출 정책 위반. (2) 캐싱(계약 §2.4)이 HTTP 경로에서는 발동하지 않음 — 매 요청 클라이언트가 이미 만든 컨텍스트를 보내므로 `run_research()` 자체가 호출되지 않음.
- **크래시는 아님**: 라우터는 기계적으로는 정상 동작(TestClient로 200 OK, 유효한 RoadmapResult 확인). 계약 문서와 코드가 어긋난 것이지 오류가 나는 것은 아니다.
- **조치**: `app/roadmap/`·`app/routers/roadmap.py`는 기능 4 담당자 소유라 임의로 수정하지 않았다(작업 규칙). 계약 §2.4대로 라우터를 고칠지, 아니면 계약을 실제 구현에 맞춰 갱신할지는 기능 4 담당자와 합의 필요 — 8절 절차로 처리해야 함.

</details>

### ✅ 해결됨 — 소스 선택 로직이 practice/trend를 크라우드아웃 (v0.7, 2026-07-13)

Tavily 키를 실제로 발급받아 `.env`에 넣은 뒤 스모크 검증하는 과정에서, 키가 정상인데도 `run_research()` 경로로는 한 번도 호출되지 않는 현상을 발견했다.

- **원인**: `service.py`의 `ADAPTERS = [semantic_scholar, arxiv, github, tavily]` 고정 순서 + `MAX_FINDINGS=8`, `PER_QUERY_LIMIT=4` 조합 때문에, semantic_scholar+arxiv(둘 다 research 소스) 결과만으로 첫 쿼리에서 이미 8건이 채워지면 github·tavily는 그 요청에서 아예 호출되지 못했다. 실제로 goal_001·goal_marketing_001·최초 Tavily 스모크에서 findings 8건이 매번 전부 `research` 타입이었던 이유가 이거였다(`tavily.search()`를 파이프라인 밖에서 직접 호출하면 정상적으로 5건이 반환되는 것으로 키 자체는 문제없음을 확인).
- **결정**: §2.9(계약 문서 참고) — 소스를 SPEC 4.3의 세 조사 대상(practice/trend/research)으로 묶은 **pillar 라운드로빈**으로 교체. 판단 기준은 사용자 요청대로 **LLM 없이 규칙 기반**(source_type 가중치: 리스트 순서 practice→trend→research가 동률 시 우선순위 + pillar별 최소 반영 보장)으로 구현했다. `service.py`의 `ADAPTERS` 상수를 `PILLARS`(pillar명, 어댑터 리스트) 튜플 목록으로, 어댑터 순차 소진 루프를 `_roundrobin()`(itertools 레시피)로 교체.
- **재검증**: 신규 `goal_id`로 실호출 → `[practice, trend, research, research, ...]` 순서로 8건 중 4건이 Tavily(trend)로 채워짐 확인(이전엔 8건 전부 research). 회귀 테스트 2건 추가(`test_practice_and_trend_not_crowded_out_by_research`, `test_pillar_roundrobin_picks_practice_and_trend_first_within_query`).
- **불변**: `run_research` 시그니처·`ResearchContext`/`Finding` 스키마·실패 계약·캐싱 정책 전부 그대로. 기존 13개 테스트도 전부 원래 로직대로 통과(핵심 흐름은 그대로, 소스 간 순서만 바뀜).

## 5. 오픈 이슈

- ~~리서치 갱신 주기~~ → 계약 v0.3 §2.4 확정: `goal_id` 단위 캐싱, 갱신 주기 자동화는 이후 스프린트
- LLM 요약 품질(현재 abstract 트림) — 정상 Gemini 키/유료 티어 확보 시 요약 단계 옵션 추가
- ~~소스 확장: GitHub·범용 검색 어댑터 추가~~ → v0.5에서 GitHub·Tavily 채택 완료(§2.7). Reddit은 상업적 이용 ToS 제약으로 기각(확정, 유료 계약 없이는 재검토 안 함)
- ~~Tavily 실 스모크 미검증~~ → v0.7에서 해결. 키 발급·투입 후 실호출로 trend findings 반영 확인(위 §4 참고)
- 한글 목표 → 영문 논문/GitHub API 쿼리 키워드 품질(현재 도구·시스템·AX 키워드 조합, LLM 키워드 추출로 승격 가능) — GitHub(practice)이 일부 목표에서 0건 반환하는 원인으로 추정
- seed findings 확장: 현재 goal_001 전용. 다른 goal_id에 대한 seed는 미준비(seed 파일 없으면 자동으로 실시간 조회만 사용 — 정상 동작)
- ~~`app/routers/roadmap.py`가 계약 §2.4 HTTP 오케스트레이션과 다름~~ → v0.6에서 해결(§4 참고)
- **`RoadmapResult` 캐싱 미구현** (신규, v0.6에서 제안): §4 "오픈 제안" 참고. 기능 4 담당자와 조율 필요(8절 절차)

## 6. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-13 | 계약 v0.7 — 소스 선택 로직을 고정 어댑터 순서에서 **pillar(practice/trend/research) 라운드로빈**으로 교체(§2.9). Tavily 키 발급 후 실호출로 정상 반영 검증, `TAVILY_API_KEY` 미설정 시 조용히 생략되던 것과 별개로 키가 있어도 크라우드아웃되던 버그 해소. `ADAPTERS`→`PILLARS`, `_roundrobin()` 신설. 회귀 테스트 2건 추가, 65 tests passed |
| 2026-07-13 | 계약 v0.6 — HTTP 오케스트레이션 계약 불일치 해소: `app/routers/roadmap.py`의 `/generate`·`/publish`·`/generate-and-publish`가 `ResearchContext`를 요청 바디로 받던 것을 제거, 서버 내부 `run_research()` 호출로 수정(비용-편익 분석 후 사용자 승인, §4 참고). origin/main(Notion 발행 기능) 병합. `RoadmapResult` 캐싱은 오픈 제안으로 남김. 함수+HTTP 레벨 통합 재검증, 63 tests passed |
| 2026-07-13 | 기능3↔4 통합 테스트(계약 §7-4 DoD) 완료 — 실제 `run_research(goal_001)` 출력을 코드 수정 없이 `generate_roadmap()`에 투입, ok/failed 양경로 검증. 통합 중 `app/routers/roadmap.py`가 계약 §2.4(HTTP 오케스트레이션·리서치 비노출)와 다르게 구현된 것을 발견(§4 기록) — 기능 4 소유 파일이라 수정하지 않고 보고만 함 |
| 2026-07-13 | v0.5 — origin/main(기능 4)과 병합, `contracts/`를 기능 4 소유 버전으로 통일. 소스 어댑터 GitHub·Tavily 추가(Reddit은 상업적 ToS 제약으로 기각). AX 리포트 6건 기반 seed findings 14건 큐레이션(URL 중복 버그 수정, `SEED_LIMIT=4` 도입). 테스트를 `test_research.py`(run_research 동작)와 `test_contracts.py`(공동 스키마, 기능 4 소유)로 분리, 44 tests passed |
| 2026-07-13 | v0.4 pivot — Gemini grounding 무료 티어 불가(404/429) 확인 → 검색 백엔드를 **다중 소스 실시간 API(Semantic Scholar + arXiv)**로 교체, LLM 요약 옵션화(핵심 경로 LLM 불필요), 큐레이션 seed findings 병합 추가. `gemini_client.py` 제거, `research/sources/`·`seed.py` 신설. 스키마·시그니처 불변 |
| 2026-07-13 | 기능 3 구현 완료 — `contracts/goal.py`·`research.py`, `fixtures/goal_001.json`·`research_context_goal_001.json`, `research/`(service·query_builder·gemini_client·filters·cache), `tests/test_contracts.py`(20 passed), `scripts/smoke_research.py`. 3절 체크리스트 전부 확정. 실제 API 실패 계약 검증됨, ok 스모크는 계정 쿼터 이슈로 보류(§4) |
| 2026-07-13 | 계약 v0.3 반영 — 리서치 캐싱 정책 확정(실시간 웹서치 + `goal_id` 단위 캐싱, `status="failed"` 미캐싱). 3절 캐싱 체크리스트 확정 처리, 5절 오픈 이슈에서 갱신 주기 이슈 종료 |
| 2026-07-11 | 계약 v0.2 반영 — 웹서치 방식(Gemini grounding)·통합 형태(모듈)·실패 계약 확정, 구현 계획 골격 추가 |
