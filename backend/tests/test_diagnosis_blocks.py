"""기능 2 산출물의 노션 렌더링 검증."""

import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MaturityDiagnosis
from app.notion.diagnosis_blocks import render_diagnosis_blocks

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _goal() -> GoalDefinition:
    return GoalDefinition.model_validate(_load("goal_001.json"))


def _diagnosis() -> MaturityDiagnosis:
    return MaturityDiagnosis.model_validate(_load("maturity_diagnosis_marketing.json"))


def _block_text(block: dict) -> str:
    payload = block[block["type"]]
    return "".join(rt.get("text", {}).get("content", "") for rt in payload.get("rich_text", []))


def test_render_diagnosis_blocks_has_gauges_and_goal():
    blocks = render_diagnosis_blocks(_diagnosis(), _goal())
    all_text = " ".join(_block_text(b) for b in blocks if "rich_text" in b.get(b["type"], {}))

    assert "우리 팀 AX 성숙도 진단" in all_text
    # 막대 게이지가 그려진다 (점수 2 → ■■□□□)
    assert "■■□□□ 2/5" in all_text
    # 목표 문장이 들어간다
    assert _goal().goal_text in all_text
    # 벤치마크는 출처와 함께 인용된다 (SPEC 2.6)
    assert "원티드 AX 인사이트 리포트" in all_text
