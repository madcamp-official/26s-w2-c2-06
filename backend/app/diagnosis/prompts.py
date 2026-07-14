"""
diagnosis/prompts.py

기능 2 프롬프트 조립. SPEC 4.2(5축 진단 + 목표 설정) · 2장(준수 정책) 근거.
"""

from app.contracts.onboarding import OnboardingData

_AXIS_RUBRIC = """
## 성숙도 5개 축 (각 1~5점, SPEC 4.2 고정)
1점=거의 없음 … 5점=잘 갖춰짐. 온보딩 데이터에 근거해 보수적으로 추정한다.

- 전략 명확성: "무엇을 AI로 바꿀지" 목표 문장이 있는가. (막연히 'AI 써야지'만 있으면 낮음)
- 도구 활용도: 팀 표준 AI 도구·프롬프트가 있는가. (개인 계정 산발적 사용이면 낮음)
- 팀 수용력: 팀원 간 활용 수준이 고르고 거부감이 낮은가. (편차가 크면 낮음)
- 데이터 접근성: 업무에 필요한 데이터에 쉽게 접근 가능한가. (흩어져 있으면 낮음)
- 평가 체계: 시간 절감·효과를 측정하는 지표가 있는가. (지표 자체가 없으면 1~2점)
"""

_POLICY = """
## 정책
- 쉬운 일상어로 쓴다. 기술 용어(RAG/파인튜닝 등) 금지.
- 목표 문장은 '문제 정의 → AI로 해결'을 담되, 전사 도입이 아니라 이 팀이 이번에 바꿀 수 있는
  범위로 잡는다. Layer 3(전략·최종 판단)은 사람이 한다는 전제를 지킨다.
- benchmark(외부 통계 비교)는 **출처를 명확히 댈 수 있을 때만** 채우고, 확신이 없으면 null로 둔다.
  숫자를 지어내지 않는다 (SPEC 2.6). 채운다면 source에 리포트명을 반드시 적는다.
"""


def _render_onboarding(onb: OnboardingData) -> str:
    tasks = "\n".join(
        f"- {t.title} (빈도: {t.frequency}, {'정형' if t.is_standardized else '비정형'}, "
        f"{t.avg_time_minutes}분, 민감정보: {t.contains_sensitive_info}, 현재방식: {t.current_method})"
        for t in onb.repetitive_tasks
    ) or "(수집된 반복 업무 없음)"
    env = onb.org_environment
    return f"""## 팀 프로필
- 업종: {onb.industry or '미상'}
- 팀 규모: {onb.team_size}명
- 담당 업무: {', '.join(onb.work_categories) or '미지정'}
- 팀장 AI 활용 수준: {onb.ai_adoption_level.value}

## 조직 환경
- 회사 AI 가이드라인: {'있음' if env.has_ai_guideline else '없음'}
- 사내 지정 AI 도구: {', '.join(env.designated_ai_tools) or '없음'}
- 외부 AI 사용 허용: {'허용' if env.external_ai_allowed else '불가/미정'}
- 팀원 간 활용 편차: {env.ai_usage_variance or '정보 없음'}

## 반복 업무
{tasks}"""


def build_diagnosis_prompt(onboarding: OnboardingData) -> str:
    return f"""당신은 중간관리자의 팀 AX(AI 전환) 성숙도를 진단하고 첫 목표를 잡아주는 코칭 어시스턴트다.
{_POLICY}
{_AXIS_RUBRIC}

{_render_onboarding(onboarding)}

## 출력 지시
1. axis_scores: 위 5개 축 각각에 대해 axis/score(1~5)/interpretation(한 줄 해석)을 낸다. 5개 축을 빠짐없이.
2. priority_axes: 점수가 낮아 먼저 손봐야 할 축을 우선순위 순으로 나열.
3. summary: 이 팀의 현재 상태를 1~2문장으로.
4. goal_text: '어떤 반복 업무의 낭비를 줄여, 팀원이 무엇에 더 집중하게 한다' 형태의 목표 한 문장.
5. benchmark: 출처 있는 외부 통계 비교가 가능하면 comment/source로, 아니면 null.
6. integrated_systems: 반복 업무의 '현재방식'에 언급된 시스템(예: ERP)만 뽑는다. 없으면 빈 배열.
"""
