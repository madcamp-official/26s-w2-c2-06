"""계정별 Notion 연결 정보를 찾아 RoadmapResult를 그 계정의 워크스페이스에 발행한다."""

from app.contracts.goal import GoalDefinition
from app.contracts.roadmap import RoadmapResult
from app.core.config import settings
from app.core.db import get_session
from app.notion.blocks import render_roadmap_blocks
from app.notion.client import create_page
from app.notion.repository import get_connection


def publish_roadmap(
    goal: GoalDefinition,
    roadmap: RoadmapResult,
    account_id: str,
    parent_page_id: str | None = None,
) -> str:
    session = get_session()
    try:
        connection = get_connection(session, account_id)
    finally:
        session.close()

    if connection is None:
        raise ValueError(
            f"계정 '{account_id}'이 Notion과 연결되어 있지 않습니다. "
            f"GET /notion/connect?account_id={account_id} 으로 먼저 연결하세요."
        )

    target_page_id = parent_page_id or connection.default_page_id
    if not target_page_id:
        raise ValueError(
            "발행할 Notion 페이지를 찾을 수 없습니다 — Notion 연결 시 integration과 공유한 페이지가 없습니다."
        )

    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Notion-Version": settings.notion_api_version,
        "Content-Type": "application/json",
    }
    blocks = render_roadmap_blocks(goal, roadmap)
    title = f"AX 로드맵 — {goal.goal_text[:50]}"
    return create_page(target_page_id, title, blocks, headers)
