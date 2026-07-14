"""
roadmap/stage_b.py

Stage B — DraftPlan을 사용자 노출용 RoadmapResult로 구조화. 검색하지 않는다.
disclaimer/goal_id/research_status는 LLM 출력에 의존하지 않고 코드에서 강제한다
(SPEC.md 4.4 고정 문구 보장 방식에 대한 담당자 결정 — FEATURE4 문서 참고).

source_refs도 같은 이유로 코드가 보완한다: gemini-3.1-flash-lite(현재 기본 모델)가
"관련 finding이 있으면 반드시 인용" 지시를 프롬프트에 명시해도 가끔 빈 배열로 응답하는
것을 실측으로 확인함(gemini-3.5-flash는 같은 입력에서 정상 인용) — 모델을 유지하기로
했으므로, LLM이 비워둔 source_refs는 키워드 겹침 기반 폴백으로 채운다(_fallback_source_refs).
"""

import re

from google import genai

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import ROLE_REASSIGNMENT_DISCLAIMER, RoadmapResult, Task
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.gemini_client import generate_structured
from app.roadmap.prompts import build_stage_b_prompt

_WORD_RE = re.compile(r"[a-zA-Z가-힣]{2,}")


def _fallback_source_refs(task: Task, research: ResearchContext, max_refs: int = 1) -> list[str]:
    """LLM이 비워둔 source_refs를 위해 task와 finding의 키워드 겹침만으로 가장 관련 있어
    보이는 finding을 골라 인용한다 — LLM 인용만큼 정교하진 않지만, 아무 근거도 안 보여주는
    것보다는 낫다는 판단(사용자 결정, 2026-07-14)."""
    if not research.findings:
        return []

    task_text = f"{task.title} {task.expected_effect} {' '.join(task.tools_needed)}".lower()
    task_keywords = set(_WORD_RE.findall(task_text))
    if not task_keywords:
        return []

    scored: list[tuple[int, str]] = []
    for finding in research.findings:
        finding_text = f"{finding.source_title} {finding.summary} {finding.relevant_method}".lower()
        finding_keywords = set(_WORD_RE.findall(finding_text))
        overlap = len(task_keywords & finding_keywords)
        if overlap > 0:
            scored.append((overlap, finding.finding_id))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [finding_id for _, finding_id in scored[:max_refs]]


def run_stage_b(
    client: genai.Client,
    draft: DraftPlan,
    goal: GoalDefinition,
    research: ResearchContext,
    onboarding: OnboardingData,
) -> RoadmapResult:
    prompt = build_stage_b_prompt(draft, goal, onboarding)
    result = generate_structured(client, prompt, RoadmapResult)

    result.goal_id = goal.goal_id
    result.research_status = research.status

    valid_member_ids = {m.member_id for m in onboarding.member_tags}
    for suggestion in result.role_reassignment_suggestions:
        suggestion.disclaimer = ROLE_REASSIGNMENT_DISCLAIMER
        # 온보딩에 실제로 없는 member_id는 LLM이 지어낸 것으로 간주하고 버린다.
        suggestion.assigned_member_ids = [
            member_id
            for member_id in suggestion.assigned_member_ids
            if member_id in valid_member_ids
        ]

    for metric in result.metrics:
        # 발행 시점엔 현재값을 갱신할 트래킹 기능이 아직 없어 기존값과 동일하게 시작한다.
        metric.current_value = metric.baseline_value

    # Stage B 프롬프트는 fitness_assessment를 다시 채우라고 지시하지 않지만, structured output은
    # 스키마 전체를 채우려 들기 때문에 Stage B가 work_item_id 등을 새로 지어낼 수 있다(실 호출로 확인:
    # wi_006처럼 Stage A가 부여하지 않은 값이 나온 적 있음). Stage A가 이미 코드로 검증한 값이 항상
    # 정본이므로 Stage B의 출력 여부와 무관하게 무조건 덮어쓴다.
    result.fitness_assessment = draft.fitness_judgments

    for task in result.tasks:
        if not task.source_refs:
            task.source_refs = _fallback_source_refs(task, research)

    return result
