# 스프린트 1 — 공통 계약 (기능 3·4)

> `SPEC.md` 4.3(BP 리서치 엔진)·4.4(맞춤 로드맵 + 평가 지표 생성)를 구현하기 위한 공통 기술 계약. 두 기능 담당자 모두 이 문서를 기준으로 작업하고, 각자의 세부 구현은 `SPRINT1_FEATURE3_BP_RESEARCH.md` / `SPRINT1_FEATURE4_ROADMAP_GENERATOR.md`에 기록한다. **이 계약이 바뀌면 두 담당자 모두에게 공유하고 이 문서를 갱신한다.**

- 최종 수정일: 2026-07-13
- 상태: v0.8 (§1.1 `OnboardingData` 예시를 실제 `app/contracts/onboarding.py` 코드 기준으로 정정 — 기능 4 담당자가 문서-코드 불일치 발견 후 코드를 기준으로 문서 수정. 스키마·시그니처 불변, 이전 v0.7 변경사항도 그대로 유지)

---

## 0. 전제

1번(온보딩 인터뷰), 2번(AX 성숙도 진단 및 목표 설정)은 이미 동작한다고 가정한다 (스프린트1 범위 아님). 스프린트1의 실제 시작점은 **2번이 만든 목표 정의서**이지, 온보딩 원본 답변이 아니다.

## 1. 시작점 예시 — 목표 정의서 (2번 산출물)

```json
{
  "goal_id": "goal_001",
  "goal_text": "Copilot이 ERP에 연동된 사내 환경에서, 팀 LLM 위키를 만들고 보고서 작성을 자동화한다",
  "org_constraints": {
    "allowed_tools": ["Copilot"],
    "integrated_systems": ["ERP"],
    "external_ai_allowed": false,
    "security_level": "high"
  },
  "candidate_tasks_from_onboarding": [
    "월간 보고서 작성",
    "신규 팀원 온보딩 설명"
  ]
}
```

이 예시처럼 목표는 이미 조직 환경(허용 도구, 연동 시스템, 보안 제약)을 담고 있고, 1번에서 수집한 반복 업무 후보도 참조로 들고 있다. 이 스키마는 `contracts/goal.py`(`GoalDefinition`)로 코드화하며, 스프린트1 동안 `fixtures/goal_001.json`을 표준 입력 픽스처로 사용한다.

### 1.1 온보딩 데이터 — `OnboardingData` (임시 스키마, v0.3 추가, v0.8에서 실제 코드 기준으로 정정)

> **⚠️ 임시(기능 1 확정 전).** 기능 1(온보딩 인터뷰)의 정식 산출물 스키마가 아직 확정되지 않았다. 아래는 기능 4 담당자가 `app/contracts/onboarding.py`에 실제로 구현·테스트해둔 스키마이며, 근거는 `SPEC.md` 4.1의 출력(팀 프로필 + 반복 업무 리스트 + 팀원 태깅)이다. 기능 1이 확정되면 8절 변경 절차로 정식화한다. 소유권은 기능 4 담당자(임시 정의자)에게 있으며 기능 3은 이 스키마를 사용하지 않는다(`run_research`의 입력은 `GoalDefinition`뿐).
>
> **v0.8 정정 사유**: v0.3에서 이 절에 적었던 예시(`team_profile` 중첩, `ai_adoption_level`, `task_name`/`is_structured`/`avg_duration_min`, `member_alias`/`workload`)는 SPEC 4.1만 보고 새로 쓴 것이라, 실제 `app/contracts/onboarding.py` 코드(평평한 구조, 아래 필드명)와 달랐다. 코드가 이미 `generate_roadmap()`·Stage A 프롬프트·테스트에 전부 연결되어 있어 코드 쪽을 기준으로 문서를 고쳤다.

```json
{
  "team_size": 8,
  "industry": "제조",
  "repetitive_tasks": [
    {
      "title": "월간 보고서 작성",
      "frequency": "주 1회 이상",
      "is_standardized": true,
      "avg_time_minutes": 180,
      "contains_sensitive_info": true,
      "current_method": "엑셀 수기 취합 후 워드 작성"
    }
  ],
  "member_tags": [
    {
      "member_id": "M1",
      "strengths": ["데이터 정리"],
      "ai_comfort_level": "높음",
      "workload_level": "중"
    }
  ]
}
```

**규약 (임시)**

- 최상위에 `team_profile` 래핑이 없다 — `team_size`/`industry`가 `OnboardingData`의 바로 아래 필드. `ai_adoption_level`(SPEC 4.1의 4단계 AI 활용 수준)은 아직 스키마에 없음 — 필요해지면 8절 절차로 추가.
- `repetitive_tasks[]`: SPEC 4.1 "반복 업무 상세"의 최소 필드(빈도/정형성/평균 소요시간/민감정보 여부/기존 처리 방식). 필드명은 `title`/`frequency`/`is_standardized`/`avg_time_minutes`/`contains_sensitive_info`/`current_method`. `frequency`는 자유 텍스트(예: "주 1회 이상"/"월 1회 이하")이며, Stage A 프롬프트가 이 문자열을 "자주/가끔" 적합성 판정 기준으로 해석한다(`app/roadmap/prompts.py`의 `_FITNESS_MATRIX_BLOCK` 참고).
- `member_tags[]`: SPEC 4.1 "(선택) 팀원 태깅" — **이름 대신 익명 식별자**(`member_id`, 예: `M1`) 사용 (SPEC 2.6·4.1 정책). 필드명은 `member_id`/`strengths`/`ai_comfort_level`/`workload_level`. 선택 항목이므로 기본값 빈 배열.
- `generate_roadmap()`가 역할 재분배 제안(SPEC 4.4)과 반복 업무 참조에 사용한다. 스프린트1 픽스처는 `app/fixtures/onboarding_001.json`(실제 존재, 위 예시와 동일 스키마). 파일 소유·검수는 기능 4 담당자 몫이다.

## 2. 아키텍처 확정 사항 (v0.2에서 결정)

스프린트1 킥오프에서 아래 3가지를 확정했다. 이 절이 두 담당자의 "누가 무엇을 하는가"에 대한 최종 답이다.

### 2.1 역할 분담: 3번 = RAG의 R, 4번 = RAG의 G

- **기능 3 = Retrieval**: 실시간 외부 조회로 외부 컨텍스트를 조사·요약해 `ResearchContext`를 만든다. **생성·판단 없음.** 로드맵을 만들거나 task를 판단하지 않는다. (검색 백엔드는 v0.4에서 다중 소스 실시간 API로 변경 — 2.5절)
- **기능 4 = Generation**: 검색하지 않는다. 목표 정의서 + `ResearchContext`만으로 Gemini API를 호출해 판정·생성한다.
- 이 경계 덕분에 3번과 4번은 서로의 내부 구현(검색 쿼리, 프롬프트)을 몰라도 병렬 개발 가능하다 — 아래 4·5절 인터페이스만 지키면 된다.

### 2.2 기능 4 내부는 2단계 파이프라인 — 단, 스프린트1은 두 단계 모두 Gemini

킥오프에서 논의된 "foundation 모델이 적합성 판정·초안 생성 / fine-tuned 모델이 초안→로드맵·task·지표 변환" 구조에 대한 결정:

- **2단계 구조는 채택한다.** Stage A(판정·초안 생성)와 Stage B(초안→구조화)를 내부 인터페이스(`DraftPlan`)로 분리한다.
- **단, 스프린트1에서는 두 단계 모두 Gemini API로 구현한다.** ML 서버의 fine-tuned 모델은 스프린트1 범위가 아니다.
  - 기각 사유: fine-tuning에 필요한 학습 데이터(실행 기록·정답 로드맵 쌍)가 현재 없다. 학습 데이터는 4.5 자산화 저장소에 실행 기록이 쌓인 뒤에야 확보 가능하므로, 그 전의 fine-tuning은 비용·일정 리스크만 크다.
  - Stage B는 **교체 가능한 슬롯**으로 설계한다(입출력을 `DraftPlan → RoadmapResult`로 고정). 이후 스프린트에서 fine-tuned 모델로 교체하더라도 3↔4 계약(본 문서 4·5절)은 변하지 않는다.
- Stage A/B의 경계 세부(예: Layer 분류를 어느 단계에서 확정할지)는 기능 4 담당자 재량이며 `SPRINT1_FEATURE4_ROADMAP_GENERATOR.md`에 기록한다. 계약 대상은 4번의 **바깥** 입출력뿐이다.

### 2.3 통합 형태: 같은 repo, 모듈 분리 (별도 서비스 아님)

- 하나의 백엔드 repo 안에서 기능 3은 `research/` 패키지, 기능 4는 `roadmap/` 패키지로 개발한다. 기능 3을 별도 HTTP 서비스로 분리하는 안은 기각 (2인 스프린트에 배포·인증 오버헤드 과다).
- 경계는 **함수 시그니처 + pydantic 스키마**로 고정한다:

```python
# research/  — 기능 3 담당자 소유
def run_research(goal: GoalDefinition) -> ResearchContext: ...

# roadmap/  — 기능 4 담당자 소유
def generate_roadmap(
    goal: GoalDefinition,
    research: ResearchContext,
    onboarding: OnboardingData,          # 4.1 반복업무·팀원 태깅
    assets: AssetStore | None = None,    # (2회차~) 4.5 자산화 저장소. 스프린트1에서는 None
) -> RoadmapResult: ...
```

- 디렉토리 소유권 (서로의 디렉토리는 수정하지 않는다):

```
app/
  contracts/    # GoalDefinition, ResearchContext, RoadmapResult 등 pydantic 스키마 — 공동 소유, 변경은 8절 절차
  research/     # 기능 3 담당자 전용
  roadmap/      # 기능 4 담당자 전용
  fixtures/     # goal_001.json, research_context_goal_001.json 등 통합용 고정 예시 — 공동 소유
tests/
  test_contracts.py   # 양쪽 출력의 스키마 검증 (공동)
```

### 2.4 HTTP 오케스트레이션 & 리서치 캐싱 (v0.3에서 결정, v0.6에서 구현 정합성 확인)

**HTTP 오케스트레이션 — 리서치 레이어는 API에 비노출.**

- `POST /roadmap/generate`는 **목표 정의서(`GoalDefinition`)와 `OnboardingData`만** 요청 바디로 받는다. `ResearchContext`를 요청 바디로 받지 않는다.
- 엔드포인트 핸들러가 내부에서 `run_research(goal)` → `generate_roadmap(goal, research, onboarding, ...)`를 **순차 호출**한다. 즉 리서치는 서버 내부 단계이며 클라이언트는 그 존재를 모른다.
- 이 원칙은 `/generate`뿐 아니라 **`/roadmap/publish`·`/roadmap/generate-and-publish`에도 동일하게 적용**한다(v0.6에서 명확화). `/publish`는 이미 생성된 `RoadmapResult`를 Notion에 재발행하는 엔드포인트이지만, 요청 바디에 `goal`(따라서 `goal_id`)이 이미 있으므로 여기서도 클라이언트가 `ResearchContext`를 직접 보내는 대신 서버가 `run_research(goal)`을 내부 호출해 인용용 컨텍스트를 재구성한다. §2.4 캐싱 덕분에 같은 `goal_id`로 이미 `/generate`가 호출된 적 있으면 즉시 캐시 히트라 추가 비용이 거의 없다.
- 근거: `SPEC.md` 4.3 — BP 리서치 엔진은 사용자에게 노출되지 않는 백엔드 리서치 레이어다. 리서치 결과를 외부로 노출/입력받는 경로를 만들지 않는다.
- 함수 시그니처(2.3절)는 그대로다. 이 절은 그 두 함수를 **HTTP 레벨에서 누가 엮는가**만 고정한다. 엔드포인트/오케스트레이션 코드는 `roadmap/`(또는 `routers/`) 소유이며, 기능 3은 `run_research()`만 제공한다.
- **v0.6 구현 완료**: 실제로는 `app/routers/roadmap.py`가 이 절과 어긋나게 구현되어(`GenerateRoadmapRequest`/`PublishRoadmapRequest`가 `ResearchContext`를 필수/옵션 필드로 요구하고 `run_research()`를 호출하지 않음) `SPRINT1_FEATURE3_BP_RESEARCH.md` §4에 "계약 불일치"로 기록되어 있었다. 비용-편익 분석(캐싱 신뢰성·수정 범위·SPEC 4.3 가중치, 상세는 FEATURE3 §4 참고) 후 라우터를 이 절대로 수정했다. 라우터는 기능 4 소유 파일이지만, 이번 수정은 사용자가 명시적으로 위임한 예외 조치다. 통합테스트(함수 레벨 + HTTP 레벨)로 재검증 완료 — `SPRINT1_FEATURE3_BP_RESEARCH.md` §4 참고.
- **오픈 제안 (미구현)**: `RoadmapResult` 자체를 `goal_id` 단위로 캐싱하면 동일 목표 재요청 시 Gemini 호출(Stage A+B, ~55~60초)까지 스킵할 수 있다. 이 캐싱은 `app/roadmap/`(기능 4 소유) 안에 둘지, 기능 3의 `research/cache.py`와 같은 패턴으로 별도 모듈을 둘지 기능 4 담당자와 조율이 필요하다 — 이번엔 라우터 수정만 반영하고 캐싱 자체는 제안으로 남긴다.

**리서치 캐싱 정책 (확정).**

- 리서치는 **실시간 웹서치**를 유지한다. 사전 구축 corpus(벡터DB) 매칭 방식은 **기각 유지**(2.1·6절, `SPEC.md` 4.3).
- 단, **동일 `goal_id` 재요청은 캐싱**하여 다시 웹서치하지 않고 이전 `ResearchContext`를 그대로 반환한다. 목표는 스프린트1 동안 갱신 주기 없이 goal_id 단위로 1회 조사 후 재사용한다(리서치 갱신 주기는 이후 스프린트에서 결정).
- 캐시 키는 `goal_id`. 구현 위치·저장 방식(인메모리/파일/DB)은 기능 3 담당자 재량이며 `SPRINT1_FEATURE3_BP_RESEARCH.md`에 기록한다. `status="failed"` 결과는 캐싱하지 않는다(다음 요청에서 재시도 가능하도록).

### 2.5 검색 백엔드 변경 — Gemini grounding → 다중 소스 실시간 API (v0.4에서 결정)

> **§8 계약 변경 절차로 처리됨** (§6 기술 스택 변경). SPEC 정책(실시간 웹서치 유지·사전 corpus 기각)은 **불변** — 바뀐 것은 "실시간 조회를 어떤 도구로 하는가"뿐이다.

- **기각 배경**: Gemini 내장 Google Search grounding은 무료 API 티어에서 사실상 사용 불가로 확인됨(발급 키에서 grounding·일반 호출 모두 404/429). grounding은 유료 티어(billing) 게이팅. 무료로 한도를 늘릴 실질적 방법 없음.
- **채택**: 검색 백엔드를 **다중 소스 실시간 API**로 교체한다. 각 소스는 요청 시점에 외부를 실시간 조회하므로 SPEC 4.3 "실시간 웹서치 기반" 정의를 충족하고, "사전 구축 corpus 매칭"이 아니다.
  - **스프린트1 범위(최소)**: 논문 API — **Semantic Scholar + arXiv** (완전 무료·안정, SPEC 4.3 "논문/연구" pillar). `source_type="research"`.
  - **이후 확장(옵션)**: GitHub Search(`practice`), 범용 검색 API(Tavily 등, `trend`). 스프린트1에는 미포함.
- **LLM 의존 제거**: 소스 API가 title/abstract/url/발행연도를 구조화된 형태로 주므로, 요약·구조화에 **LLM(Gemini)이 필수가 아니다.** 스프린트1 핵심 경로는 LLM 없이 동작(요약은 abstract 트림). LLM 요약은 유료/정상 키 확보 시 품질 향상용 **옵션**으로만 얹고, 실패 시 트림 요약으로 degrade. → 기능 3은 스프린트1에서 `GEMINI_API_KEY_RESEARCH` 없이도 동작한다(키는 옵션).
- **불변**: `run_research(goal) -> ResearchContext` 시그니처와 `ResearchContext`/`Finding` 스키마(§4)는 그대로. 소비자(기능 4)는 이 변경의 영향을 받지 않는다. `search_queries`에는 사용한 소스 쿼리를 그대로 기록.

### 2.6 큐레이션 seed findings 병합 (v0.4에서 결정)

- 웹/논문 검색에 나오지 않는 **사람이 큐레이션한 소수의 근거**(예: 메일로 받은 사내 리포트)를 `Finding`으로 정리해 `ResearchContext.findings`에 **실시간 결과와 같은 스키마로 병합**할 수 있다.
- **주 메커니즘은 실시간 조회**이며, seed는 보조다(별도 wiki/corpus-매칭 시스템을 만들지 않는다 — SPEC 4.3 corpus 기각 유지). seed는 소수로 제한한다 — **코드로 강제**: `service.SEED_LIMIT`(현재 4)만큼만 요청당 병합하고 나머지는 실시간 조회로 채운다. seed 저장 파일 자체는 그보다 많은 후보를 담아도 된다(v0.5 §2.8 참고).
- seed도 `source_url`(출처)을 갖는다(SPEC 2.6 "출처 있는 경우만 인용"). 사내 문서라 공개 URL이 없으면 내부 식별자를 넣되, 기능 4가 사용자에게 그대로 노출하지 않도록 주의(리서치 레이어 비노출 — SPEC 4.3). **동일 문서에서 여러 findings를 뽑을 때는 `internal://.../doc-id#section-slug`처럼 fragment로 구분해 URL을 고유하게 만든다** — service의 URL 기준 중복 제거 로직이 같은 URL을 가진 findings를 하나로 합쳐버리기 때문.
- 저장 위치/형식은 기능 3 담당자 재량(예: `fixtures/seed_findings_*.json`).

### 2.8 AX 리포트 6건 기반 seed 큐레이션 (v0.5에서 실행)

- 사용자가 제공한 AX 리포트 6건(뤼튼 AX Report, SK-AX MI리포트 3건, 원티드 AX 인사이트, kt cloud 트렌드 리포트)을 서브에이전트가 SPEC.md 기획 의도에 맞춰 분석해 `fixtures/seed_findings_goal_001.json`에 **14건**으로 큐레이션했다(§2.6 SEED_LIMIT=4 적용으로 요청당 최대 4건만 실제 병합).
- 선정 기준: goal_001(Copilot·ERP·LLM위키·보고서자동화·고보안) 직결 사례 우선 + AI 적합성 판정(4.4)·Layer 차등 효과·작게 시작(2.5)·AI 만능주의 경계(2.3) 등 정책 실증 근거. 출처가 불명확한 사내/유료 리포트라 전부 `internal://` 식별자 사용(공개 URL 지어내지 않음, §2.6 규약 준수).
- 뤼튼 AX Report는 리포트 자체에 "Strictly Confidential" 표기가 있어 특히 공개 URL 대체 불가 확인.

### 2.7 소스 확장 — GitHub·Tavily 채택, Reddit 기각 (v0.5에서 결정)

> §2.5에서 예고한 "이후 확장(옵션)"을 스프린트1 내에 실행. 스키마·시그니처 불변.

- **GitHub Search API 채택** (`source_type="practice"`, frontier 개인·현장 도구/프롬프트 활용법). 무료·키 불필요(검색 엔드포인트 비인증 10회/분, `GITHUB_TOKEN` 있으면 30회/분). 실 호출로 검증 완료 — goal_001 관련 쿼리에서 목표와 직접 연관된 저장소가 실제로 조회됨.
- **Tavily 채택** (`source_type="trend"`, AX 트렌드·블로그). 월 1,000 크레딧 무료(카드 불필요), `TAVILY_API_KEY` 필요. **키 미설정 시 해당 소스만 조용히 생략**(호출 자체를 안 함, 다른 소스로 degrade) — 나머지 소스는 정상 동작. `goal_id` 캐싱(§2.4)으로 크레딧 절약.
- **Reddit 기각(확정)**: Reddit Data API 무료 티어는 **비상업적 이용으로 명시적으로 제한**되며, 상업적 이용은 별도 유료 계약(연 기본 $12,000선)과 수동 승인이 필요하다. AI Champion은 실제 서비스(상업적 의도)이므로 무료 티어로 Reddit 데이터를 가져오는 것은 ToS 위반 리스크가 있다. 유료 계약 없이는 채택하지 않는다. 필요성이 커지면 유료 계약 여부를 사용자와 별도로 결정한다 — 코드로 우회 구현하지 않는다.
- ~~어댑터 우선순위: `semantic_scholar → arxiv → github → tavily` (service.py `ADAPTERS`)~~ → **v0.7에서 교체**(아래 §2.9). 개별 소스 실패/키부재는 흡수되고 나머지 소스로 자연 degrade (실패 계약과 동일한 원칙, 유지).

### 2.9 소스 선택 로직 — 고정 우선순위 → pillar 라운드로빈 (v0.7에서 결정)

**문제**: §2.7의 고정 어댑터 순서(`semantic_scholar → arxiv → github → tavily`)는 실제로는 "우선순위"가 아니라 "먼저 채운 소스가 이긴다"였다. `MAX_FINDINGS=8`, `PER_QUERY_LIMIT=4`인데 논문 소스 둘(semantic_scholar+arxiv)만으로 한 쿼리에서 최대 8건이 나올 수 있어, **실제로는 GitHub·Tavily가 같은 요청 안에서 한 번도 호출될 기회를 못 얻는 경우가 흔했다**(goal_001, 신규 goal_marketing_001 스모크에서 findings 8건이 전부 `research` 타입이었던 사례로 실증됨). Tavily 키를 발급받아 넣어도 이 구조 때문에 사실상 죽어있는 상태였다.

**결정**: `SPEC.md` 4.3의 세 조사 대상(AX 트렌드=trend, 논문/연구=research, frontier 개인 활용법=practice)을 **pillar**로 묶고, 쿼리마다 pillar 간 **라운드로빈**으로 한 건씩 채택한다.

```python
PILLARS = [
    ("practice", [github]),                    # 실무 적합도 최우선
    ("trend", [tavily]),
    ("research", [semantic_scholar, arxiv]),    # 같은 pillar 내 여러 어댑터는 연결 후 함께 라운드로빈에 참여
]
```

- **판단 기준 = 규칙 기반, LLM 미사용**: source_type(pillar)별 다양성 보장 + 리스트 순서로 동률 시 우선순위(practice > trend > research)를 표현한다. LLM으로 관련도를 점수화하는 대안도 검토했으나 기각 — 계약 §2.5(핵심 경로 LLM 불필요)를 지키고, 무료 Gemini 티어 불안정(§2.5 배경) 리스크를 다시 끌어들이지 않기 위함.
- **효과**: 후보가 8건보다 많을 때도 practice/trend가 최종 findings에서 배제되지 않는다(회귀 테스트: `tests/test_research.py::test_practice_and_trend_not_crowded_out_by_research`). 실호출 검증: 신규 goal_id로 실제 조회 시 `[practice, trend, research, research, ...]` 순서로 8건 중 4건이 trend(Tavily)로 채워짐 확인(이전에는 8건 전부 research였음).
- **불변**: `run_research` 시그니처, `ResearchContext`/`Finding` 스키마, 실패 계약(개별 어댑터 실패 흡수) — 전부 그대로. `MAX_FINDINGS`/`PER_QUERY_LIMIT`/`OK_THRESHOLD` 값도 불변.
- **오픈 이슈로 남는 것**: GitHub(practice) 쿼리가 특정 목표에서 0건을 반환하는 경우가 있음(쿼리 키워드 품질 — 기존 오픈 이슈 "한글 목표 → 영문 쿼리 키워드 품질"과 동일 원인으로 추정, 별도 조치 없음).

## 3. 전체 흐름

```
[2번] 목표 정의서 (GoalDefinition)
        │
        ▼
[3번] BP 리서치 엔진 ── run_research()
   - 역할: RAG의 "R" (검색·조사만, 생성·판단 없음)
   - 방식: 다중 소스 실시간 API (스프린트1: 논문 API = Semantic Scholar + arXiv). 사전 구축 벡터DB/corpus 아님 (2.5절)
   - 쿼리: 목표 텍스트 + 조직 제약 / 조사 대상: AX 트렌드·논문·frontier 개인 AI 활용법
   - + 소수 큐레이션 seed findings 병합 가능 (2.6절)
   - 목표 "단위"로 조사 — task 단위 아님 (task breakdown은 4번 역할)
        │  ResearchContext (4절)
        ▼
[4번] 로드맵 생성 ── generate_roadmap()
   - 역할: RAG의 "G" (생성·판단, 검색 없음)
   - 내부 2단계 (둘 다 Gemini, 2.2절):
     Stage A: AI 적합성 판정 + 실행 전략 초안 (DraftPlan)
     Stage B: DraftPlan → RoadmapResult 구조화 (structured output / 추후 fine-tuned 모델 교체 슬롯)
   - 처리 내용 (SPEC.md 4.4 그대로):
     AI 적합성 판정 → Layer 1/2/3 분류 → task breakdown → 역할 재분배 제안 → 평가 지표 설계
        │  RoadmapResult (5절)
        ├──▶ Frontend — 쉬운 언어로 표시 (SPEC.md 2.1 정책은 4번 또는 프론트 레이어 담당)
        └──▶ 5번(트래킹/자산화/평가) — 실행 baseline으로 저장 → 다음 루프의 4번 입력
```

## 4. 인터페이스 계약 — 3 → 4 (ResearchContext)

```json
{
  "goal_id": "goal_001",
  "retrieved_at": "2026-07-11T10:00:00Z",
  "status": "ok",
  "search_queries": ["팀 위키 LLM 구축 사례", "report automation copilot enterprise"],
  "findings": [
    {
      "finding_id": "F1",
      "source_title": "string",
      "source_url": "string",
      "source_type": "trend | research | practice",
      "published_date": "2026-05-01 (모르면 null)",
      "summary": "2~3문장 요약 (원문 그대로 X, 요약된 형태)",
      "relevant_method": "예: LLM 위키 활성화 조건",
      "metric_snippet": "출처가 있는 수치만, 없으면 null"
    }
  ]
}
```

**규약**

- `findings`는 **목표 단위** 조사 결과 리스트다. 목표: 3~8건. 4번이 이걸 바탕으로 task를 쪼개고 `finding_id`로 근거 인용한다 (5절 `source_refs`).
- `status`: `"ok"`(정상) / `"partial"`(일부만 확보) / `"failed"`(검색 실패, findings 빈 배열).
- **실패 계약**: 3번은 검색이 실패해도 경계 밖으로 예외를 던지지 않는다. `status="failed"` + 빈 `findings`를 반환한다. 4번은 `partial`/`failed`에서도 동작해야 한다 — 로드맵은 생성하되 외부 근거 인용 없이, 결과에 신뢰도 낮음을 표시.
- `search_queries`는 디버깅·출처 추적용이며 사용자에게 노출하지 않는다.
- 사용자에게 이 구조를 그대로 노출하지 않는다 (`SPEC.md` 4.3 정책). 출처 인용문(2.6 정책)의 원천은 `source_url` + `metric_snippet`뿐이다.

## 5. 인터페이스 계약 — 4 → Frontend / 5번 (RoadmapResult)

```json
{
  "goal_id": "goal_001",
  "research_status": "ok",
  "fitness_assessment": [
    {
      "task_candidate": "월간 보고서 작성",
      "matrix_position": "자주+정형",
      "verdict": "규칙기반 자동화 추천 (Pivot)",
      "reason": "string",
      "gate_applied": null
    }
  ],
  "tasks": [
    {
      "task_id": "task_001",
      "title": "string",
      "layer": 1,
      "week": 1,
      "difficulty": "중",
      "est_time": "string",
      "expected_effect": "string",
      "tools_needed": ["Copilot"],
      "failure_risk": "string",
      "source_refs": ["F1"]
    }
  ],
  "role_reassignment_suggestions": [
    {
      "task_id": "task_001",
      "suggested_member": "string",
      "reason": "string",
      "disclaimer": "실제 배분은 팀장님이 판단해주세요"
    }
  ],
  "metrics": [
    { "task_id": "task_001", "metric_name": "string", "baseline": "string", "target": "string" }
  ]
}
```

**규약**

- `fitness_assessment`는 SPEC.md 4.4의 "AI 적합성 판정" 결과 (Pivot 포함).
- `source_refs`는 `ResearchContext.findings[].finding_id`를 참조한다 (배열 인덱스 참조 금지 — 순서 바뀌면 깨짐).
- `week`는 주 단위 타임라인 (SPEC.md 4.4 처리 순서 3).
- `research_status`는 받은 `ResearchContext.status`를 그대로 전달 — 5번·프론트가 근거 신뢰도를 알 수 있게.
- `role_reassignment_suggestions`는 팀 내부 재분배로 한정 (SPEC.md 4.4) — `disclaimer`는 항상 고정 문구.
- 이 결과물 전체가 5번(트래킹)에 baseline으로 저장되고, 다음 루프에서 4번 재호출 시 자산화 저장소 데이터와 함께 다시 입력된다.

## 6. 기술 스택 (확정)

| 항목 | 결정 | 비고 |
|---|---|---|
| 언어/스키마 | Python 3.11+, pydantic v2 | `contracts/`에 스키마 코드화 |
| Foundation 모델 | **Gemini API** (3번·4번 공통) | 무료 티어 우선, 비용 발생 시 재검토 |
| 3번 검색 | ~~Gemini Google Search grounding~~ → **다중 소스 실시간 API** (스프린트1: Semantic Scholar + arXiv) | v0.4 변경(2.5절). grounding은 무료 티어 불가로 기각. 사전 구축 corpus 방식은 여전히 기각(확정). API별 응답에서 `source_url`·발행일 직접 추출 |
| 4번 생성 | **Gemini structured output** (responseSchema로 JSON 강제) | Stage A·B 모두. fine-tuning은 스프린트1 범위 밖 (2.2절 기각 사유 참고) |
| 통합 형태 | 같은 repo, 모듈 분리 | 별도 HTTP 서비스 기각 (2.3절) |
| API 키 (기능 3) | `GEMINI_API_KEY_RESEARCH` (**옵션**, v0.4) | 스프린트1 핵심 경로는 LLM 불필요라 키 없이도 동작. 있으면 요약 품질 향상용으로만 사용(자기 키만, 교차 참조 금지). Semantic Scholar/arXiv는 키 불필요 |
| API 키 (기능 4) | `GEMINI_API_KEY_ROADMAP` | 기능 4(`roadmap/`)가 **자기 키만** 읽는다. 기능 3 키를 참조하지 않는다 |

**API 키 정책 (v0.3 확정).**

- Gemini API 키는 **환경변수 2개로 분리**한다: `GEMINI_API_KEY_RESEARCH`(기능 3) / `GEMINI_API_KEY_ROADMAP`(기능 4). 각 모듈은 자기 키만 읽고 서로의 키를 교차 참조하지 않는다(모듈 소유권·과금 추적·rate limit 격리 목적).
- **키를 코드에 하드코딩하지 않는다.** 키는 환경변수(`.env`)에서만 읽는다. `.env`는 `.gitignore`에 유지하며 커밋하지 않는다. 발급·설정 절차는 `docs/setup/API_KEY_SETUP.md`, 템플릿은 `.env.example` 참고.

세부 구현(프롬프트 설계, 재시도/캐싱, grounding 파라미터 등)은 각자의 FEATURE 문서에서 다룬다 — 이 계약 문서에는 넣지 않는다.

## 7. 병렬 작업 프로토콜 (소통 오류 방지 장치)

1. **픽스처 우선 커밋**: 계약 확정과 동시에 `fixtures/goal_001.json`(1절 예시)과 `fixtures/research_context_goal_001.json`(4절 스키마를 채운 가짜 리서치 결과)을 커밋한다. 픽스처 작성: 3번 담당자, 검수: 4번 담당자.
2. **기능 4는 픽스처로 개발**: 3번 완성을 기다리지 않고 `research_context_goal_001.json`을 입력으로 개발·테스트한다.
3. **기능 3은 스키마 테스트로 검증**: `run_research()` 출력이 `ResearchContext` pydantic 검증을 통과하는지 `tests/test_contracts.py`로 상시 확인한다.
4. **통합 완료 기준 (스프린트1 DoD)**: 실제 `run_research(goal_001)` 출력을 `generate_roadmap()`에 넣었을 때, 픽스처 대비 코드 수정 없이 유효한 `RoadmapResult`가 나온다. `status="failed"` 경로도 1회 테스트한다.

## 8. 계약 변경 절차

- 스키마·시그니처 변경이 필요하면: **이 문서를 먼저 갱신 → 상대 담당자 확인 → `contracts/` 코드 반영** 순서. 한쪽 FEATURE 문서나 코드에서만 몰래 바꾸지 않는다.
- 필드 추가는 nullable/기본값으로 (기존 코드 안 깨지게), 필드 삭제·의미 변경은 반드시 사전 합의.

## 9. 담당자 문서

| 기능 | 문서 |
|---|---|
| 3. BP 리서치 엔진 | `SPRINT1_FEATURE3_BP_RESEARCH.md` |
| 4. 맞춤 로드맵 + 평가 지표 생성 | `SPRINT1_FEATURE4_ROADMAP_GENERATOR.md` |

## 10. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-13 | v0.8 — §1.1 `OnboardingData` 문서-코드 불일치 발견 및 정정: v0.3에서 SPEC 4.1만 보고 새로 쓴 예시(`team_profile` 중첩, `ai_adoption_level`, `task_name`/`is_structured`/`avg_duration_min`, `member_alias`/`workload`)가 실제 `app/contracts/onboarding.py`(평평한 구조, `title`/`is_standardized`/`avg_time_minutes`/`member_id`/`workload_level`)와 달랐다. 코드가 이미 `generate_roadmap()`·Stage A 프롬프트·테스트에 연결되어 있어 문서를 코드 기준으로 수정(코드 변경 없음). 기능 4에서 추가로: 로드맵 근거 인용에 `source_url` 클릭 링크·`metric_snippet` 반영(계약 §4 "출처 인용 원천은 source_url/metric_snippet" 규약 실행), `RoadmapResult`를 `goal_id`로 캐싱해 동일 목표 재요청 시 Gemini Stage A+B 재호출 생략(§2.4 "오픈 제안" 구현, `app/roadmap/cache.py`). 69 tests passed |
| 2026-07-13 | v0.7 — §2.9 신설: 소스 선택 로직을 고정 어댑터 순서(`semantic_scholar→arxiv→github→tavily`)에서 **pillar(practice/trend/research) 라운드로빈**으로 교체. research 소스 둘만으로 `MAX_FINDINGS`가 채워져 practice·trend가 크라우드아웃되던 문제 해소(LLM 미사용, 규칙 기반). `service.py`의 `ADAPTERS` 상수를 `PILLARS`로 대체. 실호출로 Tavily(trend) 정상 반영 확인. 회귀 테스트 2건 추가, 65 tests passed |
| 2026-07-13 | v0.6 — §2.4 HTTP 오케스트레이션 계약 불일치 해소: `app/routers/roadmap.py`의 `/generate`·`/publish`·`/generate-and-publish`가 `ResearchContext`를 요청 바디로 받던 것을 제거하고, 서버 내부에서 `run_research(goal)`을 호출하도록 수정(§2.4에 `/publish` 적용 범위 명확화 추가). 기능 4 소유 파일이지만 사용자가 비용-편익 분석 후 위임한 예외 조치. `RoadmapResult` 캐싱은 오픈 제안으로 남김(§2.4). origin/main(Notion 발행 기능) 병합 포함. 통합테스트(함수+HTTP 레벨) 재검증 완료, 63 tests passed |
| 2026-07-13 | v0.5 — ① **기능 4(origin/main)와 병합**: 기능 4 담당자가 독립적으로 만든 `contracts/goal.py`·`research.py`(str Enum 사용)를 채택(add/add 충돌을 기능 4 쪽으로 해소, 필드는 동일), `contracts/__init__.py`는 기능 3의 re-export 버전 유지, `core/config.py`는 기능 4의 단일 `GEMINI_API_KEY` 채택(리서치가 Gemini 불필요해졌으므로 §6의 "키 기능별 분리"는 폐기), `tests/test_contracts.py`는 기능 4의 공동 스키마 테스트를 유지하고 기능 3의 `run_research()` 동작 테스트는 `tests/test_research.py`로 분리. 병합 후 44개 테스트 전부 통과 확인 ② **소스 확장**(§2.7): GitHub Search·Tavily 채택, Reddit은 상업적 이용 ToS 제약으로 기각 ③ **seed 소수 원칙 코드화**(§2.6): `SEED_LIMIT=4` 도입 ④ AX 리포트 6건 기반 seed 14건 큐레이션(§2.8), seed 간 URL 중복으로 일부가 조용히 드롭되던 버그를 fragment URL로 수정 |
| 2026-07-13 | v0.4 — 기능 3 검색 백엔드 변경(§8 절차): Gemini Google Search grounding이 무료 API 티어에서 사용 불가(404/429, grounding 유료 게이팅)로 확인 → **다중 소스 실시간 API**로 교체(스프린트1: Semantic Scholar + arXiv). SPEC 정책(실시간 유지·사전 corpus 기각)은 불변, 도구만 변경(§2.5, §6). LLM(Gemini) 요약을 **옵션화**(핵심 경로는 LLM 없이 동작, `GEMINI_API_KEY_RESEARCH` 옵션). **큐레이션 seed findings 병합** 정책 추가(§2.6). `run_research` 시그니처·`ResearchContext`/`Finding` 스키마 불변 |
| 2026-07-13 | v0.3 — ① 리서치 캐싱 정책 확정: 실시간 웹서치 유지(사전 구축 corpus 기각 유지), 단 동일 `goal_id` 재요청은 캐싱해 재검색 안 함(2.4절) ② API 키 분리 정책 추가: `GEMINI_API_KEY_RESEARCH`/`GEMINI_API_KEY_ROADMAP` 환경변수 2개, 각 모듈 자기 키만 읽음, 하드코딩 금지(6절) ③ `OnboardingData` 임시 스키마 추가(1.1절, 기능 1 확정 전·기능 4 담당자 소유) ④ HTTP 오케스트레이션 명시: `POST /roadmap/generate`는 목표 정의서만 받고 내부에서 `run_research()`→`generate_roadmap()` 순차 호출, `ResearchContext` 비노출(2.4절) |
| 2026-07-11 | v0.2 — 아키텍처 확정: ① 기능 4는 2단계(Stage A 판정·초안 / Stage B 구조화) 설계하되 스프린트1은 둘 다 Gemini, fine-tuning은 범위 밖(교체 슬롯만 유지) ② 같은 repo 모듈 분리(별도 서비스 기각) ③ 3번 웹서치는 Gemini Google Search grounding. ResearchContext에 `status`/`finding_id`/`source_type` 등 추가, RoadmapResult에 `week`/`research_status` 추가, 실패 계약·병렬 작업 프로토콜(7절)·변경 절차(8절) 신설 |
