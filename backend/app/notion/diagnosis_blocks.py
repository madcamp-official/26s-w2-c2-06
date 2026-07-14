"""
notion/diagnosis_blocks.py

기능 2 산출물(MaturityDiagnosis + 목표 정의서)을 노션 블록으로 렌더링한다. 기능 3·4의 로드맵
블록과 같은 페이지에 얹혀(→ publish.publish_report) "우리 팀은 지금 여기 있고, 그래서 이 목표를
이렇게 실행한다"는 하나의 흐름을 만든다.

노션에는 레이더 차트 블록이 없어서, 5개 축을 **막대 게이지**(■/□)로 그려 한눈에 비교할 수 있게 한다.
톤 가이드는 blocks.py와 동일 (해요체·쉬운 언어·SPEC 2장).
"""

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MATURITY_AXES, MaturityDiagnosis
from app.notion.rich_text import (
    bold_text,
    bulleted,
    callout,
    divider,
    heading2,
    quote,
    text,
)

_BAR_FILLED = "■"
_BAR_EMPTY = "□"
_MAX_SCORE = 5


def _gauge(score: int) -> str:
    score = max(0, min(_MAX_SCORE, score))
    return _BAR_FILLED * score + _BAR_EMPTY * (_MAX_SCORE - score)


def _axis_line(axis_label: str, score: int, interpretation: str) -> dict:
    """한 축을 '전략 명확성  ■■□□□ 2/5 — 해석' 한 줄로."""
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                bold_text(f"{axis_label}  "),
                text(f"{_gauge(score)} {score}/{_MAX_SCORE}"),
                text(f"  — {interpretation}" if interpretation else ""),
            ]
        },
    }


def render_diagnosis_blocks(diagnosis: MaturityDiagnosis, goal: GoalDefinition) -> list[dict]:
    blocks: list[dict] = [heading2("우리 팀 AX 성숙도 진단")]

    if diagnosis.summary:
        blocks.append(callout(diagnosis.summary, icon="🧭"))

    # 5개 축 게이지 (정규 순서대로 — service에서 이미 정렬돼 오지만 방어적으로 한 번 더)
    scores_by_axis = {s.axis: s for s in diagnosis.axis_scores}
    for axis in MATURITY_AXES:
        s = scores_by_axis.get(axis)
        if s is None:
            continue
        blocks.append(_axis_line(axis.value, s.score, s.interpretation))
    # 정규 축에 없던 항목도 빠뜨리지 않고 표시
    for s in diagnosis.axis_scores:
        if s.axis not in MATURITY_AXES:
            blocks.append(_axis_line(s.axis.value, s.score, s.interpretation))

    if diagnosis.priority_axes:
        order = " → ".join(a.value for a in diagnosis.priority_axes)
        blocks.append(
            callout(f"먼저 손보면 좋은 순서예요: {order}", icon="🎯")
        )

    if diagnosis.benchmark is not None:
        blocks.append(
            quote(f"{diagnosis.benchmark.comment} (출처: {diagnosis.benchmark.source})")
        )

    blocks.append(divider())
    blocks.append(heading2("그래서 이번 목표는"))
    blocks.append(callout(goal.goal_text, icon="🚩"))

    constraints = goal.org_constraints
    constraint_bits = []
    if constraints.allowed_tools:
        constraint_bits.append(f"허용 도구: {', '.join(constraints.allowed_tools)}")
    if constraints.integrated_systems:
        constraint_bits.append(f"연동 시스템: {', '.join(constraints.integrated_systems)}")
    constraint_bits.append(
        "외부 AI 사용: " + ("가능" if constraints.external_ai_allowed else "제한")
    )
    constraint_bits.append(f"보안 수준: {constraints.security_level}")
    blocks.append(bulleted(" · ".join(constraint_bits)))

    return blocks
