# 스프린트 1 — 공통 계약 (기능 3·4)

> `SPEC.md` 4.3(BP 리서치 엔진)·4.4(맞춤 로드맵 + 평가 지표 생성)를 구현하기 위한 공통 기술 계약. 두 기능 담당자 모두 이 문서를 기준으로 작업하고, 각자의 세부 구현은 `SPRINT1_FEATURE3_BP_RESEARCH.md` / `SPRINT1_FEATURE4_ROADMAP_GENERATOR.md`에 기록한다. **이 계약이 바뀌면 두 담당자 모두에게 공유하고 이 문서를 갱신한다.**

- 최종 수정일: 2026-07-11
- 상태: v0.2 (아키텍처·기술 스택·인터페이스 확정. 담당자는 확정 사항에 이견 시 8절 변경 절차로 제기)

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

## 2. 아키텍처 확정 사항 (v0.2에서 결정)

스프린트1 킥오프에서 아래 3가지를 확정했다. 이 절이 두 담당자의 "누가 무엇을 하는가"에 대한 최종 답이다.

### 2.1 역할 분담: 3번 = RAG의 R, 4번 = RAG의 G

- **기능 3 = Retrieval**: 실시간 웹서치로 외부 컨텍스트를 조사·요약해 `ResearchContext`를 만든다. **생성·판단 없음.** 로드맵을 만들거나 task를 판단하지 않는다.
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

## 3. 전체 흐름

```
[2번] 목표 정의서 (GoalDefinition)
        │
        ▼
[3번] BP 리서치 엔진 ── run_research()
   - 역할: RAG의 "R" (검색·조사만, 생성·판단 없음)
   - 방식: Gemini API + Google Search grounding (실시간 웹서치, 사전 구축 벡터DB 아님)
   - 쿼리: 목표 텍스트 + 조직 제약 / 조사 대상: AX 트렌드·논문·frontier 개인 AI 활용법
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
| 3번 웹서치 | **Gemini 내장 Google Search grounding** | 별도 검색 API 키 불필요. grounding metadata에서 `source_url` 추출. 사전 구축 corpus 방식 기각(확정) |
| 4번 생성 | **Gemini structured output** (responseSchema로 JSON 강제) | Stage A·B 모두. fine-tuning은 스프린트1 범위 밖 (2.2절 기각 사유 참고) |
| 통합 형태 | 같은 repo, 모듈 분리 | 별도 HTTP 서비스 기각 (2.3절) |

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
| 2026-07-11 | v0.2 — 아키텍처 확정: ① 기능 4는 2단계(Stage A 판정·초안 / Stage B 구조화) 설계하되 스프린트1은 둘 다 Gemini, fine-tuning은 범위 밖(교체 슬롯만 유지) ② 같은 repo 모듈 분리(별도 서비스 기각) ③ 3번 웹서치는 Gemini Google Search grounding. ResearchContext에 `status`/`finding_id`/`source_type` 등 추가, RoadmapResult에 `week`/`research_status` 추가, 실패 계약·병렬 작업 프로토콜(7절)·변경 절차(8절) 신설 |
