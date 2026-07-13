# 스프린트 1 — 기능 4: 맞춤 로드맵 + 평가 지표 생성

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4~5절 인터페이스 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 4 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.4.

- 최종 수정일: 2026-07-11
- 상태: 계약 v0.2 반영 (구현 계획 골격 확정, 세부는 담당자가 채움)

---

## 1. 이 기능이 하는 일 (계약 요약)

- **입력**: 목표 정의서 + 3번의 `ResearchContext` + 온보딩의 반복업무·팀원 태깅(4.1) + (2회차 이후) 5번 자산화 저장소 — 코드 경계는 `generate_roadmap()` 함수 하나 (계약 2.3절). 스프린트1에서 자산화 저장소 인자는 `None`
- **하는 일**: Gemini API 호출로 아래를 순서대로 생성·판단. **RAG의 "G"만 담당 — 웹서치하지 않는다**
  1. AI 적합성 판정 (빈도×정형성 매트릭스 + 게이트 → Pivot 카드)
  2. Layer 1/2/3 분류
  3. 목표 → task breakdown (주 단위 타임라인, `week` 필드)
  4. 팀 내 역할 재분배 제안 (경량 스코프 — 팀 내부만, 실행권한 없음)
  5. 평가 지표 설계
- **하지 않는 일**: 웹서치/외부 조사 (3번의 역할), 실제 트래킹·코칭 (5번의 역할)
- **출력**: `RoadmapResult` (계약 5절 스키마) → Frontend + 5번

## 2. 확정 사항 (계약 v0.2에서 결정됨)

- [x] **"ML 서버에서 fine-tuning한 형식" 해석 확정**: 실제 fine-tuning은 스프린트1에서 하지 않는다. 학습 데이터(실행 기록↔정답 로드맵 쌍)가 4.5 자산화 저장소에 쌓이기 전이므로 시기상조. 대신 아래 2단계 구조로 설계해 Stage B를 **fine-tuned 모델 교체 슬롯**으로 남긴다 — 교체하더라도 3↔4 계약은 불변 (계약 2.2절)
- [x] foundation 모델: **Gemini API** + structured output(responseSchema로 JSON 스키마 강제), 두 단계 모두
- [x] 내부 2단계 파이프라인:
  - **Stage A — 판정·초안 생성**: 목표 정의서 + `ResearchContext` + 온보딩 데이터 → AI 적합성 판정(매트릭스+게이트, Pivot 카드) + 실행 전략 초안 (`DraftPlan`, 아래 3절)
  - **Stage B — 구조 변환**: `DraftPlan` → `RoadmapResult` (task 필드 상세화, 역할 재분배 카드, 평가 지표 산출)
- [x] `ResearchContext.status`가 `partial`/`failed`여도 동작: 로드맵은 생성하되 `source_refs` 없이, `research_status`로 신뢰도 전달 (계약 4절 실패 계약)
- [x] 통합 형태: 같은 repo `roadmap/` 패키지
- [x] 픽스처 검수 책임: `fixtures/research_context_goal_001.json` 검수는 4번 담당자 (계약 7절) — 3번 완성을 기다리지 않고 이 픽스처로 개발 시작

## 3. 내부 인터페이스 — DraftPlan (기능 4 내부 전용, 계약 아님)

Stage A → Stage B 사이의 스키마. **기능 4 담당자가 단독으로 변경 가능** (3번 담당자 합의 불필요 — 계약 대상은 바깥 입출력뿐). 초안:

```json
{
  "goal_id": "goal_001",
  "fitness_judgments": [ "…RoadmapResult.fitness_assessment와 동일 구조…" ],
  "strategy_draft": "적합 판정된 업무들에 대한 서술형 실행 전략. 근거는 [F1] 형태로 finding_id 인용",
  "task_outline": [
    { "title": "string", "layer": 2, "week": 1, "approach": "string", "source_refs": ["F1"] }
  ],
  "metric_ideas": ["string"],
  "reassignment_notes": ["string"]
}
```

- Stage A가 판정과 Layer·주차 배치까지 결정하고, Stage B는 구조·필드 완성(난이도/소요시간/실패요인/지표 baseline·target)을 담당하는 것을 1차 기준으로 한다. 경계 조정은 담당자 재량, 조정 시 이 절 갱신
- fine-tuned 모델로 Stage B를 교체할 때의 학습 입출력 쌍이 곧 (`DraftPlan`, `RoadmapResult`)가 되므로, 이 스키마를 안정적으로 유지할수록 나중 fine-tuning 데이터 수집이 쉬워진다

## 4. 담당자 확인·결정 사항 (남은 체크리스트)

- [x] `RoadmapResult` 스키마 최종 검토 — 계약 문서 스키마 그대로 `app/contracts/roadmap.py`에 코드화. 변경 없음
- [x] AI 적합성 판정 매트릭스의 구체 임계값 — **"자주" = 주 1회 이상 수행, "가끔" = 그보다 드묾**(`app/roadmap/prompts.py`의 `_FITNESS_MATRIX_BLOCK`에 명시해 Stage A 프롬프트에 포함). 정형성은 `OnboardingData.RepetitiveTask.is_standardized` 불리언 값을 그대로 사용
- [~] task granularity 기준 — "이번 주 바로 시도 가능한 수준"이라는 정성적 지시만 프롬프트에 포함(`week` 필드로 주 단위 배치). 정량 기준(예: 최대 소요시간)은 아직 미정 — 실사용 피드백 나오면 재조정
- [ ] 평가 지표 산식 (시간 단축 측정 방법) — 아직 고정 공식 없음. 현재는 Stage B가 baseline/target을 텍스트로 생성(LLM 판단에 위임). 4.5 자산화 저장소에 실행 기록이 쌓이기 전까지는 확정 어려움 — 오픈 이슈로 유지
- [x] `ResearchContext.findings` 프롬프트 주입 방식 — **전체 삽입**으로 결정 (findings 3~8건이라 토큰 부담 적음). `app/roadmap/prompts.py`의 `build_stage_a_prompt`에서 전체 findings를 순회해 인용 가능하도록 주입
- [x] Stage A/B 프롬프트 설계, structured output 스키마 정의 — `app/roadmap/prompts.py`(프롬프트) + `app/roadmap/draft_plan.py`(`DraftPlan`, Stage A↔B 내부 스키마) + `app/contracts/roadmap.py`(`RoadmapResult`, Stage B 출력). Gemini 호출은 `google-genai` SDK의 `client.models.generate_content(config=GenerateContentConfig(response_mime_type="application/json", response_schema=<pydantic model>))` 패턴 사용 (`app/roadmap/gemini_client.py`)
- [x] SPEC.md 2.1(쉬운 언어)·2.2(Layer 원칙 문구)·4.4 고정 disclaimer 보장 위치 — **쉬운 언어·Layer 원칙은 프롬프트 텍스트**(`_POLICY_BLOCK`)로 지시하고, **disclaimer 고정 문구는 LLM 출력에 의존하지 않고 `app/roadmap/stage_b.py`의 후처리 코드에서 강제 덮어쓰기**로 100% 보장 (LLM이 문구를 틀리거나 누락해도 항상 정확한 문구가 나가도록). 같은 이유로 `goal_id`/`research_status`도 코드에서 강제

## 5. 구현 계획 (골격 — 담당자가 세부 채움)

1. [x] **픽스처 기반 개발 착수**: `app/fixtures/goal_001.json`(계약 1절 예시 그대로) + `app/fixtures/research_context_goal_001.json`(계약 4절 예시를 goal_001 시나리오로 구체화, findings 3건) 작성. **주의**: 원래 계약 7절은 이 픽스처의 "작성"을 3번(리서치) 담당자 몫으로 정했는데, 3번 담당자가 아직 착수 전이라 4번 개발을 막지 않기 위해 임시로 초안을 만들었다 — **3번 담당자 확정되면 검수/교체 필요**. `onboarding_001.json`도 같은 이유로 임시 작성(1번 담당자 미정)
2. [x] **Stage A**: `app/roadmap/stage_a.py::run_stage_a()` — 적합성 판정+전략 초안+task outline을 `DraftPlan`으로 생성 (structured output). `goal_id`는 LLM 출력과 무관하게 코드에서 강제
3. [x] **Stage B**: `app/roadmap/stage_b.py::run_stage_b()` — `DraftPlan` → `RoadmapResult` 변환. disclaimer·`goal_id`·`research_status` 후처리, `fitness_assessment` 비어있으면 Stage A 결과로 폴백
4. [x] **검증**: `tests/test_contracts.py`(스키마+픽스처 검증, `failed` 상태 경로 포함), `tests/test_roadmap_stage_a.py`/`test_roadmap_stage_b.py`/`test_roadmap_service.py`/`test_roadmap_router.py` — Gemini는 가짜 클라이언트(`tests/conftest.py::FakeClient`)로 대체해 네트워크 없이 오케스트레이션 검증. `source_refs`가 실제 `finding_id`인지 검사하는 테스트는 아직 없음 — 오픈 이슈로 남김
5. [ ] **통합**: 실제 `run_research()` 출력으로 교체해 DoD 확인 (계약 7절 4항) — 3번 담당자 구현 대기 중. 지금은 임시 픽스처로만 검증했고, **실제 Gemini API 호출 자체도 아직 라이브로 검증 못함**(API 키 대기 중, 6절 참고)

## 6. 오픈 이슈 (SPEC.md 4.4에서 이관)

- 지표 산식 (시간 단축 측정 방법) — 미확정, 4.5 실행 기록 축적 후 재검토
- task granularity 정량 기준 — 정성적 지시만 적용, 정량화는 추후
- 3번 담당자의 실제 `research_context_goal_001.json`으로 교체 후 통합 테스트 (DoD)
- `source_refs`가 실제 존재하는 `finding_id`를 참조하는지 검증하는 테스트 추가

## 7. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-11 | 계약 v0.2 반영 — fine-tuning 해석 확정(스프린트1 미실시, Stage B 교체 슬롯로 설계), 내부 2단계 파이프라인·DraftPlan 스키마 초안·구현 계획 골격 추가 |
| 2026-07-13 | Stage A/B 구현 완료: `app/contracts/`(goal·research·roadmap·onboarding·assets), `app/roadmap/`(gemini_client·draft_plan·prompts·stage_a·stage_b·service), `app/routers/roadmap.py`, 픽스처 3종, 테스트 5개 파일(가짜 Gemini 클라이언트로 오케스트레이션만 검증, 실제 API 호출은 미검증). 적합성 매트릭스 임계값·findings 주입 방식·disclaimer 보장 위치 확정. SDK는 `google-generativeai`가 아닌 신규 `google-genai` 사용 |
