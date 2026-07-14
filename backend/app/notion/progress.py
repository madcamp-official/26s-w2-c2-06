"""Opportunity Map/Roadmap 데이터베이스를 다시 읽어와 대시보드의 집계 콜아웃 2개를 갱신한다 (수동 새로고침).

Notion 공개 API는 데이터베이스 전체를 대상으로 한 차트/집계 뷰를 만들 수 없어서(9절 참고),
"발견한 AI Opportunity 수"/"AX 적용한 업무 수"는 이 함수가 매번 다시 세어서 콜아웃 텍스트를
덮어쓴다 — 실시간 자동 반영이 아니라 이 함수(엔드포인트)를 호출해야 갱신된다. task별 `Progress %`는
이와 달리 Notion formula 속성이라 여기서 손댈 필요가 없다(Notion이 알아서 계산).
"""

from app.core.config import settings
from app.core.db import get_session
from app.notion.client import query_data_source, update_callout_text
from app.notion.repository import get_connection
from app.notion.tracking_repository import get_workspace


def _number_prop(row: dict, name: str) -> float | None:
    return row["properties"][name]["number"]


def _select_name(row: dict, name: str) -> str | None:
    select = row["properties"][name]["select"]
    return select["name"] if select else None


def refresh_dashboard_stats(account_id: str) -> dict:
    session = get_session()
    try:
        workspace = get_workspace(session, account_id)
        if workspace is None:
            raise ValueError(f"계정 '{account_id}'에 발행된 대시보드가 없습니다.")
        connection = get_connection(session, account_id)
    finally:
        session.close()

    if connection is None:
        raise ValueError(f"계정 '{account_id}'의 Notion 연결이 사라졌습니다.")

    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Notion-Version": settings.notion_api_version,
        "Content-Type": "application/json",
    }

    work_items = query_data_source(workspace.opportunity_data_source_id, headers)
    discovered = sum(1 for row in work_items if _select_name(row, "적합성") != "부적합")

    tasks = query_data_source(workspace.roadmap_data_source_id, headers)
    applied = 0
    for row in tasks:
        baseline = _number_prop(row, "기존값")
        current = _number_prop(row, "현재값")
        if baseline is not None and current is not None and current != baseline:
            applied += 1

    if workspace.discovered_count_block_id:
        update_callout_text(
            workspace.discovered_count_block_id,
            f"발견한 AI Opportunity 수: {discovered}건 (전체 업무 {len(work_items)}건 중, 새로고침 기준)",
            headers,
        )
    if workspace.applied_count_block_id:
        update_callout_text(
            workspace.applied_count_block_id,
            f"AX 적용한 업무 수: {applied}건 (전체 task {len(tasks)}건 중, 새로고침 기준)",
            headers,
        )

    return {
        "discovered": discovered,
        "total_work_items": len(work_items),
        "applied": applied,
        "total_tasks": len(tasks),
    }
