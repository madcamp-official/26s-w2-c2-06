"""
roadmap/notion_blocks.py

RoadmapResult -> Notion 블록. 여기서 "우리 서비스의 톤"을 결정한다.

## 톤 가이드 (참고: 토스의 8가지 라이팅 원칙 + docs/SPEC.md 2장 정책)
- 해요체, 능동태, 긍정형 문장 (SPEC.md 2.1 "쉬운 언어" + 토스 원칙 그대로 채택)
- 기술 용어 금지: RAG/파인튜닝/임베딩 등을 노출하지 않는다 (SPEC.md 2.1)
- Layer 3(전략/의사결정)에는 항상 "최종 판단은 팀장님의 몫"임을 명시 (SPEC.md 2.2)
- 전사 도입 언어 금지 — "이번 주에 팀원 1~2명과 시도해볼 수 있는 것"이라는 뉘앙스 유지 (SPEC.md 2.5)
- Pivot(부적합) 판정도 실패가 아니라 "지금은 다른 방법이 낫다"는 긍정적 프레이밍으로 전달
- 근거 있는 수치만 인용하고, 확정적 어투("반드시 성공합니다") 대신 권유형 어투 사용 (SPEC.md 2.6)

이 파일은 순수 렌더링만 담당한다 (Notion API 호출은 notion_client.py).
"""

from app.contracts.goal import GoalDefinition
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import RoadmapResult


def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": content}}


def _paragraph(content: str) -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": [_text(content)]}}


def _heading2(content: str) -> dict:
    return {"type": "heading_2", "heading_2": {"rich_text": [_text(content)]}}


def _heading3(content: str) -> dict:
    return {"type": "heading_3", "heading_3": {"rich_text": [_text(content)]}}


def _callout(content: str, icon: str = "💡") -> dict:
    return {
        "type": "callout",
        "callout": {"rich_text": [_text(content)], "icon": {"emoji": icon}},
    }


def _bulleted(content: str) -> dict:
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_text(content)]}}


def _todo(content: str) -> dict:
    return {"type": "to_do", "to_do": {"rich_text": [_text(content)], "checked": False}}


def _intro_paragraph(goal: GoalDefinition) -> str:
    return (
        f'"{goal.goal_text}"를 위한 첫 로드맵을 준비했어요. '
        "한 번에 다 하지 않아도 괜찮아요 — 이번 주에 팀원 1~2명과 가볍게 시도해볼 수 있는 것부터 "
        "골라보시고, 아래 내용은 팀장님이 최종 판단하실 때 참고할 자료로 봐주세요."
    )


def _fitness_block(verdict: str, task_candidate: str, reason: str) -> dict:
    is_fit = "적합" in verdict or "Pivot" not in verdict
    icon = "✅" if is_fit else "🔄"
    return _callout(f"{task_candidate}\n판정: {verdict}\n{reason}", icon=icon)


def render_roadmap_blocks(goal: GoalDefinition, roadmap: RoadmapResult) -> list[dict]:
    blocks: list[dict] = [_paragraph(_intro_paragraph(goal))]

    if roadmap.research_status != ResearchStatus.OK:
        blocks.append(
            _callout(
                "이번 로드맵은 참고할 외부 사례를 일부만 확인했어요. "
                "실행해보시면서 저희와 함께 조정해나가요.",
                icon="⚠️",
            )
        )

    if roadmap.fitness_assessment:
        blocks.append(_heading2("이 업무들, AI로 풀어도 될까요?"))
        for fa in roadmap.fitness_assessment:
            blocks.append(_fitness_block(fa.verdict, fa.task_candidate, fa.reason))

    if roadmap.tasks:
        blocks.append(_heading2("이번 로드맵"))
        for week in sorted({t.week for t in roadmap.tasks}):
            blocks.append(_heading3(f"{week}주차"))
            for task in [t for t in roadmap.tasks if t.week == week]:
                blocks.append(
                    _todo(f"[Layer {task.layer}] {task.title} · {task.est_time} · 난이도 {task.difficulty}")
                )
                blocks.append(_bulleted(f"기대 효과: {task.expected_effect}"))
                if task.tools_needed:
                    blocks.append(_bulleted(f"필요 도구: {', '.join(task.tools_needed)}"))
                blocks.append(_bulleted(f"미리 알아두면 좋은 점: {task.failure_risk}"))

    if roadmap.role_reassignment_suggestions:
        blocks.append(_heading2("역할 재분배 제안"))
        for s in roadmap.role_reassignment_suggestions:
            blocks.append(_callout(f"{s.suggested_member}님: {s.reason}\n\n💬 {s.disclaimer}", icon="🙋"))

    if roadmap.metrics:
        blocks.append(_heading2("어떻게 확인해볼까요?"))
        for m in roadmap.metrics:
            blocks.append(_bulleted(f"{m.metric_name} — 지금은 {m.baseline}, 목표는 {m.target}"))

    return blocks
