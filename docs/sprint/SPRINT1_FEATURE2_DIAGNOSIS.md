# 스프린트 1 — 기능 2 상세 구현 (AX 성숙도 진단 및 목표 설정)

> `SPEC.md` 4.2(AX 성숙도 진단 및 목표 설정)의 세부 구현 문서. 공통 계약은 `SPRINT1_CONTRACT.md` 참고.
> 산출물은 **둘**이다: ① 성숙도 진단(`MaturityDiagnosis`) — 노션 페이지 표시용, ② 목표 정의서
> (`GoalDefinition`) — 기능 3·4의 입력.

- 최종 수정일: 2026-07-14
- 상태: v1.0 (기능 2 최초 구현. 계약 §1의 `GoalDefinition`을 실제로 **생성**하는 주체 확정)

---

## 1. 목적과 경계

- **입력**: 기능 1의 `OnboardingData`.
- **출력**: `DiagnosisResult { maturity: MaturityDiagnosis, goal: GoalDefinition }`.
- **하는 것**: 5축 성숙도 진단 + "문제 정의 → AI로 해결" 목표 문장 도출.
- **안 하는 것**: 업무를 task로 쪼개거나 적합성 판정(기능 4), 외부 리서치(기능 3).

## 2. 성숙도 진단 — 5축 (SPEC 4.2 고정)

전략 명확성 / 도구 활용도 / 팀 수용력 / 데이터 접근성 / 평가 체계. 각 1~5점 + 해석 코멘트.

- 점수는 온보딩 데이터 근거로 **Gemini가 추정**한다(`prompts.py`의 축별 루브릭). 규칙 기반 산식이
  아니라 정성 데이터(편차·가이드라인 유무·지표 존재 여부)를 종합 판단해야 해서 LLM으로 처리한다.
- `axis_scores`는 service가 SPEC 정규 순서(`MATURITY_AXES`)로 재정렬한다 — 레이더 차트 축 순서를 고정.
- `benchmark`(외부 통계 비교)는 **출처를 댈 수 있을 때만** 채우고 확신 없으면 `null`. 숫자를 지어내지
  않는다 (SPEC 2.6). 노션 렌더링은 benchmark를 `출처: …`와 함께 인용문으로만 표시.

노션 표시: 레이더 차트 블록이 없어 `notion/diagnosis_blocks.py`가 **막대 게이지**(`■■□□□ 2/5`)로 그린다.

## 3. 목표 설정 — LLM 판단 / 결정론적 사실값 분리

`GoalDefinition`을 만들 때 **판단**과 **사실값**을 나눈다 (SPEC 2.6 — LLM이 조직 제약을 지어내지 않게):

| 필드 | 출처 |
|---|---|
| `goal_text` | Gemini (문제 정의 → 해결 문장) |
| `org_constraints.allowed_tools` | 온보딩 `org_environment.designated_ai_tools` (결정론적) |
| `org_constraints.external_ai_allowed` | 온보딩 `org_environment.external_ai_allowed` (결정론적) |
| `org_constraints.integrated_systems` | 반복 업무 `current_method`에서 LLM이 **추출**(예: ERP) |
| `org_constraints.security_level` | 규칙(§3.1) |
| `candidate_tasks_from_onboarding` | 온보딩 반복 업무 제목 그대로 |
| `goal_id` | `goal_<uuid8>` 생성 (진단·목표가 같은 id 공유) |

### 3.1 보안 수준 규칙 (`_security_level`)

기능 4의 게이트("민감정보 + 회사 가이드라인 없음 → 보류·경고")와 정합하도록 보수적으로 잡는다:

| 민감정보 업무 | 회사 가이드라인 | security_level |
|---|---|---|
| 있음 | 없음 | **high** |
| 있음 | 있음 | medium |
| 없음 | 없음 | medium |
| 없음 | 있음 | low |

회귀: `tests/test_diagnosis.py::test_security_level_rule`.

## 4. 처리 흐름 / 엔드포인트

```
[POST /diagnosis/diagnose]  OnboardingData → DiagnosisResult(maturity, goal)     ← 기능 2 코어
[POST /diagnosis/publish-report]  goal + diagnosis (+roadmap?) → 노션 한 페이지 발행
[POST /diagnosis/generate-and-publish]  OnboardingData → 진단·목표 → run_research → generate_roadmap → 노션
```

- `generate-and-publish`가 1→2→3→4→노션 전체 파이프라인이다. 리서치 레이어(기능 3)는 계약 §2.4대로
  클라이언트에 노출하지 않고 서버 내부에서만 호출한다.
- 노션 한 페이지에 **진단(레이더 게이지 + 목표)** 을 먼저, 그 뒤에 **로드맵**을 붙인다
  (`publish.publish_report`). 로드맵 블록 앞에 진단을 끼우면서 진행 추적 블록 인덱스를 밀어준다
  (`_prefix_layout`) — 안 그러면 `refresh-progress`가 엉뚱한 블록을 읽는다. 회귀:
  `tests/test_diagnosis_blocks.py::test_prefix_layout_offsets_tracked_indices`.

## 5. 파일

| 파일 | 역할 |
|---|---|
| `contracts/maturity.py` | `MaturityDiagnosis`(5축) — **공동 소유**, 계약에 신설 |
| `diagnosis/prompts.py` | 진단·목표 프롬프트 (축 루브릭 + 정책) |
| `diagnosis/draft.py` | LLM 출력 스키마(`DiagnosisDraft`) — 기능 2 내부 |
| `diagnosis/service.py` | `diagnose_and_set_goal()` — LLM 판단 + 결정론적 사실값 조립 |
| `notion/diagnosis_blocks.py` | 진단·목표 노션 렌더링(막대 게이지) |
| `notion/publish.py::publish_report` | 진단 + 로드맵을 한 페이지로 발행 |
| `routers/diagnosis.py` | HTTP 엔드포인트 3개 |
| `fixtures/maturity_diagnosis_marketing.json` | 진단 산출물 표준 픽스처 |

## 6. 해소된 SPEC 오픈 이슈

- SPEC 4.2 "축별 점수 산출 기준(문항·배점)" → **온보딩 데이터 기반 LLM 추정 + 정규 순서 정렬**로 확정.
  규칙 산식 대신 정성 데이터 종합 판단이 필요한 축들이라 LLM으로 처리(축 루브릭은 `prompts.py`).
- "우선순위 도출 로직" → `priority_axes`(보통 저점 축 우선)를 진단 출력에 포함.
- 벤치마크는 출처 있을 때만(SPEC 2.6) — 없으면 `null`, 노션에 미표시.
