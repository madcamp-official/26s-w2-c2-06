"""
notion/blocks.py

RoadmapResult -> Notion 페이지 블록. task마다 별도 페이지/데이터베이스로 쪼개지 않고,
**하나의 페이지 안에서 체크박스로 접었다 펼치는 방식**으로 만든다 — 체크박스 줄에는 task 이름만
대표로 보이고, 완료 여부를 그 자리에서 체크할 수 있다. 펼치면 상세 가이드·담당 제안까지 다 보인다
(표/데이터베이스는 페이지 이동이 필요해서 "한눈에 보기 어렵다"는 피드백으로 폐기함).
지표가 있는 task는 "체크박스 | 지표 패널"을 좌우 컬럼으로 나란히 배치해 눈으로 바로 비교할 수 있게 한다.

체크박스 상태는 Notion이 자동으로 재계산해주지 않는다 (그러려면 데이터베이스 rollup/formula가
필요한데 그건 이미 폐기한 방식) — 그래서 진행 현황 요약(_stats_callout)은 발행 시점의 스냅샷이고,
실제로 갱신하려면 `POST /roadmap/{page_id}/refresh-progress`를 호출해야 한다 (progress.py 참고).
이 파일은 그 갱신에 필요한 블록 위치(RoadmapPageLayout)도 함께 계산해서 넘겨준다.

## 톤 가이드 (참고: 토스의 8가지 라이팅 원칙 + docs/SPEC.md 2장 정책)
- 해요체, 능동태, 긍정형 문장 (SPEC.md 2.1 "쉬운 언어" + 토스 원칙 그대로 채택)
- 기술 용어 금지: RAG/파인튜닝/임베딩 등을 노출하지 않는다 (SPEC.md 2.1)
- Layer 3(전략/의사결정)에는 항상 "최종 판단은 팀장님의 몫"임을 명시 (SPEC.md 2.2)
- 전사 도입 언어 금지 — "이번 주에 팀원 1~2명과 시도해볼 수 있는 것"이라는 뉘앙스 유지 (SPEC.md 2.5)
- Pivot(부적합) 판정도 실패가 아니라 "지금은 다른 방법이 낫다"는 긍정적 프레이밍으로 전달
- 근거 있는 수치만 인용하고, 확정적 어투("반드시 성공합니다") 대신 권유형 어투 사용 (SPEC.md 2.6)

이 파일은 순수 렌더링만 담당한다 (Notion API 호출은 client.py).
"""

from dataclasses import dataclass, field

from app.contracts.goal import GoalDefinition
from app.contracts.research import ResearchContext, ResearchStatus
from app.contracts.roadmap import RoadmapResult, Task
from app.notion.guide_parser import render_guide_blocks
from app.notion.rich_text import (
    bulleted_rich,
    callout,
    checkable,
    columns,
    divider,
    heading2,
    heading3,
    labeled_paragraph,
    link_text,
    paragraph,
    table_of_contents,
    text,
)

_LAYER_ICON = {1: "🟢", 2: "🟡", 3: "🔴"}


@dataclass
class TaskBlockPosition:
    top_level_index: int
    wrapped_in_column: bool


@dataclass
class RoadmapPageLayout:
    blocks: list[dict]
    stats_block_index: int | None = None
    task_positions: dict[str, TaskBlockPosition] = field(default_factory=dict)


def _intro_paragraph(goal: GoalDefinition) -> str:
    return (
        f'"{goal.goal_text}"를 위한 첫 로드맵을 준비했어요. '
        "한 번에 다 하지 않아도 괜찮아요 — 이번 주에 팀원 1~2명과 가볍게 시도해볼 수 있는 것부터 "
        "골라보시고, 아래 내용은 팀장님이 최종 판단하실 때 참고할 자료로 봐주세요."
    )


def _fitness_block(verdict: str, task_candidate: str, reason: str) -> dict:
    is_fit = "적합" in verdict or "Pivot" not in verdict
    icon = "✅" if is_fit else "🔄"
    return callout(f"{task_candidate}\n판정: {verdict}\n{reason}", icon=icon)


def _stats_text(completed: int, total: int, tasks: list[Task]) -> str:
    weeks = sorted({t.week for t in tasks})
    week_range = f"{weeks[0]}주차" if len(weeks) == 1 else f"{weeks[0]}~{weeks[-1]}주차"
    return f"진행 현황: 완료 {completed}/{total} · {week_range}에 걸쳐 진행 (새로고침 시점 기준)"


def _resolve_source_refs(task: Task, research: ResearchContext | None) -> list[dict]:
    """근거를 실제로 클릭해서 확인할 수 있게 source_url을 링크로 건다.
    ResearchContext 자체(search_queries 등)는 노출하지 않는다 — 인용의 출처는
    source_url/metric_snippet뿐이라는 계약 §4 규약을 따른다."""
    findings_by_id = {f.finding_id: f for f in research.findings} if research else {}
    entries = []
    for ref in task.source_refs:
        finding = findings_by_id.get(ref)
        if finding is None:
            entries.append(bulleted_rich([text(f"({ref})")]))
            continue
        spans = [link_text(finding.source_title, finding.source_url), text(f" — {finding.summary}")]
        if finding.metric_snippet:
            spans.append(text(f" ({finding.metric_snippet})"))
        entries.append(bulleted_rich(spans))
    return entries


def _task_checkbox(task: Task, roadmap: RoadmapResult, research: ResearchContext | None) -> dict:
    icon = _LAYER_ICON.get(task.layer, "⚪")
    label = f"{icon} {task.title}"

    children: list[dict] = [
        labeled_paragraph("예상 소요시간 · 난이도", f"{task.est_time} · {task.difficulty}"),
        labeled_paragraph("기대 효과", task.expected_effect),
    ]

    if task.tools_needed:
        children.append(labeled_paragraph("필요 도구", ", ".join(task.tools_needed)))

    for suggestion in roadmap.role_reassignment_suggestions:
        if suggestion.task_id != task.task_id:
            continue
        children.append(
            callout(f"{suggestion.suggested_member}님: {suggestion.reason}\n\n💬 {suggestion.disclaimer}", icon="🙋")
        )

    children.append(heading3("상세 가이드"))
    children += render_guide_blocks(task.detailed_guide)

    children.append(labeled_paragraph("미리 알아두면 좋은 점", task.failure_risk))

    if task.source_refs:
        children.append(heading3("참고한 리서치 자료"))
        children += _resolve_source_refs(task, research)

    return checkable(label, children)


def _metric_panel(task: Task, roadmap: RoadmapResult) -> dict | None:
    metrics = [m for m in roadmap.metrics if m.task_id == task.task_id]
    if not metrics:
        return None
    lines = "\n".join(f"{m.metric_name}\n{m.baseline} → {m.target}" for m in metrics)
    return callout(lines, icon="📈")


def render_roadmap_page_blocks(
    goal: GoalDefinition, roadmap: RoadmapResult, research: ResearchContext | None = None
) -> RoadmapPageLayout:
    blocks: list[dict] = [paragraph(_intro_paragraph(goal))]

    if roadmap.tasks or roadmap.fitness_assessment:
        blocks.append(table_of_contents())

    if roadmap.research_status != ResearchStatus.OK:
        blocks.append(
            callout(
                "이번 로드맵은 참고할 외부 사례를 일부만 확인했어요. "
                "실행해보시면서 저희와 함께 조정해나가요.",
                icon="⚠️",
            )
        )

    if roadmap.fitness_assessment:
        blocks.append(heading2("이 업무들, AI로 풀어도 될까요?"))
        for fa in roadmap.fitness_assessment:
            blocks.append(_fitness_block(fa.verdict, fa.task_candidate, fa.reason))

    stats_block_index: int | None = None
    task_positions: dict[str, TaskBlockPosition] = {}

    if roadmap.tasks:
        blocks.append(divider())
        blocks.append(heading2("이번 로드맵"))
        stats_block_index = len(blocks)
        blocks.append(callout(_stats_text(0, len(roadmap.tasks), roadmap.tasks), icon="📊"))

        for week in sorted({t.week for t in roadmap.tasks}):
            blocks.append(heading3(f"{week}주차"))
            for task in [t for t in roadmap.tasks if t.week == week]:
                task_checkbox = _task_checkbox(task, roadmap, research)
                metric_panel = _metric_panel(task, roadmap)
                task_positions[task.task_id] = TaskBlockPosition(
                    top_level_index=len(blocks), wrapped_in_column=metric_panel is not None
                )
                if metric_panel is None:
                    blocks.append(task_checkbox)
                else:
                    blocks.append(columns([task_checkbox], [metric_panel]))

    return RoadmapPageLayout(
        blocks=blocks, stats_block_index=stats_block_index, task_positions=task_positions
    )
