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
) -> RoadmapResult:
    prompt = build_stage_b_prompt(draft, goal)
    result = generate_structured(client, prompt, RoadmapResult)

    result.goal_id = goal.goal_id
    result.research_status = research.status
    for suggestion in result.role_reassignment_suggestions:
        suggestion.disclaimer = ROLE_REASSIGNMENT_DISCLAIMER
    if not result.fitness_assessment:
        result.fitness_assessment = draft.fitness_judgments
    for task in result.tasks:
        if not task.source_refs:
            task.source_refs = _fallback_source_refs(task, research)

    return result
