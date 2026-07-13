"""계정별 Notion 연결 정보를 찾아 RoadmapResult를 그 계정의 워크스페이스에 발행한다.

한 페이지 안에 모든 내용을 담는다 (task는 체크박스로 접었다 펼침 — blocks.py 참고).
발행 후에는 실제로 생성된 체크박스/요약 블록의 ID를 다시 조회해서 DB에 저장해둔다.
Notion은 체크박스를 체크해도 다른 블록을 자동으로 갱신해주지 않기 때문에, 나중에
`progress.py`의 새로고침이 이 ID들로 체크 상태를 읽어와 요약을 다시 써준다.
"""

from app.contracts.goal import GoalDefinition
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.core.config import settings
from app.core.db import get_session
from app.notion.blocks import RoadmapPageLayout, TaskBlockPosition, render_roadmap_page_blocks
from app.notion.client import create_page, get_block_children
from app.notion.repository import get_connection
from app.notion.tracking_repository import TrackedTask, save_published_roadmap


def _resolve_task_checkbox_id(
    top_children: list[dict], position: TaskBlockPosition, headers: dict[str, str]
) -> str:
    block = top_children[position.top_level_index]
    if not position.wrapped_in_column:
        return block["id"]
    column_list_children = get_block_children(block["id"], headers)
    left_column_children = get_block_children(column_list_children[0]["id"], headers)
    return left_column_children[0]["id"]


def publish_roadmap(
    goal: GoalDefinition,
    roadmap: RoadmapResult,
    account_id: str,
    research: ResearchContext | None = None,
    parent_page_id: str | None = None,
) -> dict:
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

    title = f"AX 로드맵 — {goal.goal_text[:50]}"
    layout = render_roadmap_page_blocks(goal, roadmap, research)
    page = create_page(target_page_id, title, layout.blocks, headers)

    if layout.task_positions:
        _track_published_tasks(page["id"], account_id, layout, roadmap, headers)

    return {"url": page["url"], "page_id": page["id"]}


def _track_published_tasks(
    page_id: str,
    account_id: str,
    layout: RoadmapPageLayout,
    roadmap: RoadmapResult,
    headers: dict[str, str],
) -> None:
    top_children = get_block_children(page_id, headers)

    stats_block_id = (
        top_children[layout.stats_block_index]["id"] if layout.stats_block_index is not None else None
    )
    tracked_tasks = [
        TrackedTask(
            task_id=task.task_id,
            title=task.title,
            checkbox_block_id=_resolve_task_checkbox_id(
                top_children, layout.task_positions[task.task_id], headers
            ),
        )
        for task in roadmap.tasks
        if task.task_id in layout.task_positions
    ]

    session = get_session()
    try:
        save_published_roadmap(session, page_id, account_id, stats_block_id, tracked_tasks)
    finally:
        session.close()
