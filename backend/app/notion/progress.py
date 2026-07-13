"""발행된 로드맵의 체크박스 상태를 다시 읽어와 진행 현황 요약을 갱신한다 (수동 새로고침).

Notion은 체크박스를 체크해도 다른 블록을 자동으로 재계산해주지 않는다 — 그래서 이 함수를
호출해야 요약이 실제 체크 상태를 반영한다 (실시간 자동 반영이 아님, 문서화 필요).
"""

from app.core.config import settings
from app.core.db import get_session
from app.notion.client import get_block, update_callout_text
from app.notion.repository import get_connection
from app.notion.tracking_repository import get_published_roadmap


def refresh_progress(page_id: str) -> dict:
    session = get_session()
    try:
        published = get_published_roadmap(session, page_id)
        if published is None:
            raise ValueError(f"발행 기록을 찾을 수 없는 페이지입니다: {page_id}")

        connection = get_connection(session, published.account_id)
    finally:
        session.close()

    if connection is None:
        raise ValueError(f"계정 '{published.account_id}'의 Notion 연결이 사라졌습니다.")

    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Notion-Version": settings.notion_api_version,
        "Content-Type": "application/json",
    }

    total = len(published.tasks)
    completed_tasks = [
        task for task in published.tasks if get_block(task.checkbox_block_id, headers)["to_do"]["checked"]
    ]
    completed = len(completed_tasks)

    if published.stats_block_id:
        update_callout_text(
            published.stats_block_id,
            f"진행 현황: 완료 {completed}/{total} (새로고침 기준, 실시간 아님)",
            headers,
        )

    return {
        "completed": completed,
        "total": total,
        "completed_task_titles": [task.title for task in completed_tasks],
    }
