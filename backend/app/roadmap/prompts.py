"""
roadmap/prompts.py

Stage A/B 프롬프트 문자열 조립. 로직(Gemini 호출)과 분리해서 이 파일에서만 관리한다.
정책 근거는 docs/SPEC.md 2장(준수 정책)·4.4절(적합성 판정 매트릭스).
"""

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.roadmap.draft_plan import DraftPlan

_POLICY_BLOCK = """
## 반드시 지킬 정책
- 기술 용어(RAG, 파인튜닝, 임베딩 등)를 쓰지 말고 비유·일상어로 풀어 설명한다.
- Layer 1(반복·정형): 결과를 바로 활용 가능한 수준으로 생성.
  Layer 2(비정형·판단 필요): 초안/보조자료만 생성하고 사람이 채워야 할 지점을 명확히 표시.
  Layer 3(전략·의사결정): 정보 정리와 선택지 제시까지만 하고 "최종 판단은 사용자의 몫"임을 항상 명시.
  Layer 3에 대해 AI가 결론을 대신 내리는 것처럼 보이는 표현은 금지.
- 팀원 간 신뢰·조직문화 이슈처럼 AI로 풀 수 없는 문제는 자동화 대상에서 제외하고 그 이유를 밝힌다.
- 추상적 조언 대신 "지금 바로 복사해서 쓸 수 있는" 구체적 다음 행동을 우선한다.
- 전사 도입/큰 예산이 필요한 제안은 하지 않는다. 항상 "이번 주에 팀원 1~2명과 시도해볼 수 있는 것"부터 제안하고,
  이후 주차는 "1주차 결과를 팀에 짧게 공유 -> 2주차에 인원/업무 1개씩 추가" 식으로 점진적으로 넓혀간다
  (한 번에 팀 전체·여러 업무를 동시에 시작하는 제안 금지).
- 검증되지 않은 통계를 확정적으로 제시하지 않는다 (출처가 있는 경우만 인용). 타사 사례의 절감 수치를
  인용할 때는 반드시 "타사 사례, 참고용"이라고 명시하고, 이 팀의 목표치(target)처럼 단정해서 제시하지 않는다.
  이 팀 자체의 실행 결과 수치는 아직 없으므로 baseline은 온보딩 데이터 기반으로 적되, 실행 후 성과는
  "측정 예정"으로 남기고 확정된 숫자처럼 만들어내지 않는다.
- 인사 평가·해고 등 인사상 불이익과 직결되는 자동화는 제안하지 않는다.
- 역할 재분배를 제안할 때는 "이미 AI를 잘 쓰는 사람"에게만 몰아주지 말고, 그 사람과
  "지금 반복 업무 부담이 가장 큰 사람"을 함께 고려한다 (편차가 이미 큰 팀에서 편차를 더 벌리지 않기 위함).
"""

_FITNESS_MATRIX_BLOCK = """
## AI 적합성 판정 매트릭스
반복 업무마다 "빈도 x 정형성"으로 분류하고, 그 결과를 적합/부분 적합/부적합 3단계(fitness)로 정규화한다.
- 빈도 기준: 주 1회 이상 수행 = "자주", 그보다 드물면(예: 월 1회 이하) = "가끔"
- 정형성 기준: 온보딩 데이터의 is_standardized=true면 "정형", false면 "비정형"

| 빈도 x 정형성 | verdict | fitness | layer |
|---|---|---|---|
| 자주 + 정형 | 규칙기반 자동화(엑셀 함수/템플릿) 추천, 생성형 AI는 과함 (Pivot) | 부적합 | null |
| 자주 + 비정형 | 생성형 AI 최적 영역 | 적합 | 업무의 판단 개입 정도로 1~3 결정 |
| 가끔 + 정형 | 자동화 투자 대비 효율 낮음, 현행 유지 추천 (Pivot) | 부적합 | null |
| 가끔 + 비정형 | 케이스바이케이스, 우선순위 낮게 참고자료로만 | 부분 적합 | 업무의 판단 개입 정도로 1~3 결정 |

**정형·비정형이 섞인 업무**: 업무 하나에 "정형적인 부분"과 "판단이 필요한 비정형 부분"이 섞여 있으면
(예: "캠페인 성과 리포트" = 데이터 취합(정형) + 결과 해석(비정형)), fitness_judgments는 그 업무
[wi_xxx] 하나에 대해 **1건만** 판정한다(work_item_id는 항상 업무 1개당 1건 — 쪼개서 새 항목을
만들지 말 것. Opportunity Map 관계 키라 개수가 어긋나면 깨진다). 대신 reason에 "부분은 정형이라
자동화로 충분하고 부분은 비정형이라 AI 보조가 필요하다"처럼 혼재 사실을 구체적으로 밝힌다. 두 갈래를
실제로 다르게 다루고 싶으면 task_outline에서 같은 work_item_id 아래 접근 방식이 다른 task 여러 개
(예: "데이터 취합은 엑셀 매크로로", "결과 해석은 AI 초안 보조로")로 나눠 반영한다.

게이트(판정을 강등, fitness는 항상 부적합으로):
- 민감정보 포함(contains_sensitive_info=true) + 회사 AI 가이드라인 없음(org_constraints로 판단) -> "보류 + 경고"
- 이미 기존 대안으로 충분히 처리되고 있음 -> "현행 유지"

fitness=부적합인 항목에는 반드시 이유와 함께 **구체적인 대안**을 reason에 적는다(Opportunity Map의
"pivot 사유"로 그대로 쓰인다) — "수작업 유지"처럼 뭉뚱그리지 말고 "구글시트 함수/피벗 템플릿"
"자동 집계 매크로"처럼 실제로 쓸 수 있는 도구·방법을 이름으로 짚어준다. 보류(게이트 적용) 판정도
마찬가지로 "왜 위험한지"와 "가이드라인 생기기 전까지 무엇을 유지해야 하는지"를 구체적으로 적는다.
layer는 fitness가 적합/부분 적합일 때만 채우고, 부적합이면 null로 둔다.

## frequency_bucket
각 업무의 원문 빈도 표현(예: "주 2회", "월말마다")을 읽고 매일 / 매주 / 격주 / 월 1~2회 중 가장 가까운
하나로 분류해 frequency_bucket에 채운다(Opportunity Map 화면에 그대로 노출되는 값).
"""

_CATEGORY_GUIDE_BLOCK = """
## task 카테고리 (category, 5종 중 정확히 하나)
- Tool: 개인 생산성 도구화 — 프롬프트/템플릿 만들기, 이메일 초안 자동화, 재사용 가능한 프롬프트 라이브러리
- Automation: 규칙적 반복 작업의 자동 처리 — ERP/데이터 요약, 반복 보고서 생성, 데이터 정리
- Knowledge: 팀 지식을 AI가 찾을 수 있게 구조화 — LLM 위키, FAQ, 문서 체계
- Workflow: 업무 절차 자체의 재설계 — 승인 절차 단축, 회의→Action Item 자동화
- Culture: 팀의 AI 활용 문화 확산 — 활용 사례 수집, 데모데이, 베스트 프랙티스 공유
"""


def build_stage_a_prompt(
    goal: GoalDefinition, research: ResearchContext, onboarding: OnboardingData
) -> str:
    tasks_block = "\n".join(
        f"[wi_{i + 1:03d}] {t.title} (빈도: {t.frequency}, 정형여부: {'정형' if t.is_standardized else '비정형'}, "
        f"평균 소요시간: {t.avg_time_minutes}분, 민감정보 포함: {t.contains_sensitive_info}, "
        f"현재 처리방식: {t.current_method})"
        for i, t in enumerate(onboarding.repetitive_tasks)
    ) or "(반복 업무 후보 없음)"

    findings_block = "\n".join(
        f"[{f.finding_id}] {f.source_title} — {f.summary} (관련 방법론: {f.relevant_method}"
        + (f", 수치: {f.metric_snippet}" if f.metric_snippet else "")
        + ")"
        for f in research.findings
    ) or "(외부 리서치 결과 없음 — 근거 인용 없이 진행하고 신뢰도가 낮음을 감안할 것)"

    member_block = "\n".join(
        f"- {m.member_id}: 강점 {', '.join(m.strengths) or '없음'}, "
        f"AI 활용 편안함: {m.ai_comfort_level}, 업무부담: {m.workload_level}"
        for m in onboarding.member_tags
    ) or "(팀원 태깅 없음 — 역할 재분배 제안 생략 가능)"

    return f"""당신은 중간관리자를 돕는 AX(AI 전환) 코칭 어시스턴트다.
{_POLICY_BLOCK}
{_FITNESS_MATRIX_BLOCK}
{_CATEGORY_GUIDE_BLOCK}

## 목표
{goal.goal_text}

## 조직 제약
- 허용 도구: {', '.join(goal.org_constraints.allowed_tools) or '없음'}
- 연동 시스템: {', '.join(goal.org_constraints.integrated_systems) or '없음'}
- 외부 AI 허용 여부: {goal.org_constraints.external_ai_allowed}
- 보안 수준: {goal.org_constraints.security_level}
- (회사 AI 가이드라인 유무는 명시되지 않았다면 "없음"으로 간주하고 게이트 판정에 반영할 것)

## 팀의 반복 업무 후보 (부서 업무 전체 — 각 항목의 [wi_xxx] 태그를 그대로 인용할 것)
{tasks_block}

## 팀원 태깅 (역할 재분배 참고용, 인사 데이터 아님)
{member_block}

## 외부 리서치 컨텍스트 (research_status={research.status.value})
{findings_block}

## 출력 지시
1. fitness_judgments: 위 반복 업무 후보 **각각에 대해 정확히 1건씩, 나열된 순서 그대로** 매트릭스를 적용해
   판정. work_item_id에는 그 업무의 [wi_xxx] 태그를 그대로 적는다(새로 만들지 말 것). fitness/layer/
   frequency_bucket도 함께 채운다. 정형+비정형이 섞인 업무는 위 "정형·비정형이 섞인 업무" 지침대로
   1건으로 판정하고 reason에 혼재 사실을 적을 것(항목을 쪼개지 말 것).
2. strategy_draft: 적합/부분 적합 판정된 업무들의 서술형 실행 전략. 근거는 [F1] 형식으로 인용
   (research_status가 ok가 아니면 인용 생략). "1주차: 팀원 1명+업무 1개로 시작 -> 2주차: 결과 공유 후
   확대" 식의 점진적 확산 흐름을 문장에 담을 것
3. task_outline: 적합/부분 적합 판정된 업무를 "이번 주 바로 시도 가능한" 수준으로 나눈 task
   (work_item_id는 그 task가 구체화한 업무의 [wi_xxx] 태그, title/layer/week/category/approach/source_refs).
   **source_refs는 선택이 아니다** — 위 "외부 리서치 컨텍스트"에 이 task와 조금이라도 관련된 finding이
   있으면(같은 도구/업무 유형/업종이면 관련 있다고 간주) 반드시 그 finding_id(예: "F1")를 source_refs에
   넣어라. research_status가 ok인데 관련 finding이 하나도 없는 극히 드문 경우에만 source_refs를 비워둔다
4. metric_ideas: 성과 지표 아이디어 문장 목록 — 소요시간에 한정하지 않는다(정확도/건수/오류율 등도 가능).
   타사 벤치마크 수치를 참고했다면 "(타사 사례 참고)"를 붙이고, 이 팀의 실행 결과는 아직 없으므로 목표
   (target) 문구에 확정된 남의 숫자를 그대로 베끼지 말 것
5. reassignment_notes: 팀원 태깅을 참고한 역할 재분배 아이디어 (팀 내부 한정, 실행권한 없음을 전제로 서술).
   특정 팀원을 지목할 때는 반드시 member_id(M1, M2 …)를 그대로 언급할 것(새 이름 만들지 말 것). 위 정책의
   "이미 잘 쓰는 사람 + 부담 큰 사람 함께 고려" 원칙을 반영할 것
"""


def build_stage_b_prompt(
    draft: DraftPlan, goal: GoalDefinition, onboarding: OnboardingData
) -> str:
    outline_block = "\n".join(
        f"- [{t.work_item_id}] {t.title} (layer {t.layer}, week {t.week}, category {t.category.value}): "
        f"{t.approach} [근거: {', '.join(t.source_refs) or '없음'}]"
        for t in draft.task_outline
    ) or "(task 없음)"

    member_ids_block = ", ".join(m.member_id for m in onboarding.member_tags) or "(팀원 태깅 없음)"

    return f"""당신은 Stage A의 초안(DraftPlan)을 사용자에게 보여줄 구조화된 로드맵으로 다듬는다.
{_POLICY_BLOCK}

## 목표
{goal.goal_text}

## Stage A 실행 전략 초안
{draft.strategy_draft}

## Stage A task 개요 (work_item_id/category는 그대로 유지해서 옮길 것)
{outline_block}

## Stage A 지표 아이디어
{"; ".join(draft.metric_ideas) or "(없음)"}

## Stage A 역할 재분배 메모
{"; ".join(draft.reassignment_notes) or "(없음)"}

## 배정 가능한 팀원 ID (이 목록에 없는 ID는 절대 만들지 말 것)
{member_ids_block}

## 조직이 실제 쓸 수 있는 도구
허용 도구: {', '.join(goal.org_constraints.allowed_tools) or '명시 안 됨'}

## 출력 지시
1. tasks: 위 task 개요 각각을 difficulty(난이도)/est_time(예상 소요시간)/expected_effect(기대 효과)/
   tools_needed(필요 도구, 조직 제약의 허용 도구 우선 고려)/failure_risk(실패 요인)까지 채운 완전한 task로 확장.
   work_item_id/category는 task 개요에 적힌 값을 그대로 옮긴다(변경 금지). task_id는 "task_001"부터 순번으로 부여.
2. detailed_guide (제일 중요, 길게 써도 됨): **이 업무를 한 번도 안 해본 사람**이 그대로 따라 할 수 있는
   단계별 가이드를 작성한다.
   - **형식을 반드시 지킬 것**: 각 단계는 항상 줄바꿈으로 구분하고, 반드시 아라비아 숫자 + 마침표 +
     띄어쓰기(`"1. "`, `"2. "`, `"3. "`) 로만 시작한다. "1단계", "Step 1", "첫째" 같은 다른 표현은
     쓰지 않는다 (뒤에서 이 번호를 기준으로 자동으로 파싱해서 체크리스트로 바꾸기 때문).
   - tools_needed에 적은 도구가 처음 쓰는 도구라고 가정하고, "어디서 로그인하는지 / 계정·라이선스를
     어떻게 받는지 / 첫 화면에서 뭘 눌러야 하는지"부터 설명한다. 예:
     ```
     1. IT팀에 Copilot 라이선스를 요청한다
     2. copilot.microsoft.com에 회사 계정으로 로그인한다
     3. ...
     ```
   - AI 도구를 쓰는 단계에는 **그대로 복사해서 붙여넣을 수 있는 예시 프롬프트**를 그 단계 안에서
     큰따옴표로 감싸서 반드시 포함한다 (예: `4. Copilot 채팅창에 다음과 같이 입력한다: "다음 회의록을
     참고해서 팀 전체가 이해하기 쉬운 3줄 요약을 만들어줘: {{회의록 내용}}"`)
   - 전문 용어를 쓰면 그 자리에서 바로 풀어서 설명한다 (SPEC.md 2.1 정책과 동일)
   - 단계는 최소 4~5개 이상으로 세분화한다. "그냥 Copilot으로 초안 작성" 같은 뭉뚱그린 문장 금지.
3. role_reassignment_suggestions: 역할 재분배 메모를 task_id와 연결한 제안 카드로 변환. task 하나당 최대
   1건, assigned_member_ids에는 "배정 가능한 팀원 ID" 목록에 실제로 있는 값만 0개 이상 넣는다(지어내지 말 것).
   disclaimer 필드에는 반드시 "실제 배분은 팀장님이 판단해주세요"를 그대로 적을 것.
4. metrics: 지표 아이디어를 task_id와 연결해 구체화한다. metric_name(지표명)·unit(단위, 예: 분/건/%)·
   baseline_value(기존값)·target_value(목표값)를 숫자로 채운다(current_value는 신경쓰지 않아도 됨 — 코드가
   baseline_value와 동일하게 채운다). 소요시간이 아니어도 된다 — 그 task에 가장 적합한 지표를 자유롭게 고른다.
5. fitness_assessment: Stage A의 fitness_judgments를 그대로 옮긴다 (내용 변경 금지).
"""
