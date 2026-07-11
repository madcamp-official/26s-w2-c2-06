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

- [ ] `RoadmapResult` 스키마 최종 검토 — 변경 필요 시 계약 8절 절차 (CONTRACT 먼저 갱신 → 3번 담당자 확인)
- [ ] AI 적합성 판정 매트릭스의 구체 임계값 (예: "자주" = 주 1회 이상?)
- [ ] task granularity 기준 (하나의 task = "이번 주 바로 시도 가능한" 수준 — SPEC.md 2.4·2.5 준수, 구체 기준 정의)
- [ ] 평가 지표 산식 (시간 단축 측정 방법 등)
- [ ] `ResearchContext.findings` 프롬프트 주입 방식 (전체 삽입 vs 선별 — findings가 3~8건이므로 1차는 전체 삽입으로 충분할 가능성 높음)
- [ ] Stage A/B 프롬프트 설계, structured output 스키마 정의
- [ ] SPEC.md 2.1(쉬운 언어)·2.2(Layer 원칙 문구)·4.4 고정 disclaimer를 프롬프트/후처리 어디서 보장할지

## 5. 구현 계획 (골격 — 담당자가 세부 채움)

1. **픽스처 기반 개발 착수**: `fixtures/goal_001.json` + `research_context_goal_001.json`으로 Stage A 프롬프트 개발
2. **Stage A**: 적합성 판정(매트릭스+게이트) → Pivot/적합 분기 → 적합 업무의 전략 초안·task outline 생성 (structured output으로 `DraftPlan` 강제)
3. **Stage B**: `DraftPlan` → `RoadmapResult` 변환 (structured output), disclaimer 고정 문구·`research_status` 전달 등 후처리
4. **검증**: pydantic 스키마 검증, `source_refs`가 실제 존재하는 `finding_id`인지 검사, `status="failed"` 입력 경로 테스트
5. **통합**: 실제 `run_research()` 출력으로 교체해 DoD 확인 (계약 7절 4항)

## 6. 오픈 이슈 (SPEC.md 4.4에서 이관)

- 지표 산식 (시간 단축 측정 방법)
- task granularity 기준
- 적합성 판정 매트릭스의 구체 임계값

## 7. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-11 | 계약 v0.2 반영 — fine-tuning 해석 확정(스프린트1 미실시, Stage B 교체 슬롯로 설계), 내부 2단계 파이프라인·DraftPlan 스키마 초안·구현 계획 골격 추가 |
