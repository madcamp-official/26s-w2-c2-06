"""계정별 Notion 연결 정보를 찾아 RoadmapResult를 그 계정의 워크스페이스(Opportunity Map/Roadmap/팀원
데이터베이스 + 대시보드 페이지)에 발행한다. 발행 직후 대시보드 집계 콜아웃도 한 번 새로고침한다.

v0.9에서 "페이지+체크박스" 방식(옛 `blocks.py`)을 데이터베이스 upsert 방식(`sync.py`)으로 교체했다
— 상세 설계는 `SPRINT1_FEATURE4_ROADMAP_GENERATOR.md` 9절 참고.
"""

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MaturityDiagnosis
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.core.config import settings
from app.core.db import get_session
from app.notion.progress import refresh_dashboard_stats
from app.notion.repository import get_connection
from app.notion.sync import sync_roadmap


def _headers_for(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": settings.notion_api_version,
        "Content-Type": "application/json",
    }


def publish_roadmap(
    goal: GoalDefinition,
    roadmap: RoadmapResult,
    onboarding: OnboardingData,
    account_id: str,
    parent_page_id: str | None = None,
    research: ResearchContext | None = None,
) -> dict:
    session = get_session()
    try:
        connection = get_connection(session, account_id)
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

        workspace = sync_roadmap(
            goal,
            roadmap,
            onboarding,
            account_id,
            target_page_id,
            session,
            _headers_for(connection.access_token),
            research,
        )
    finally:
        session.close()

    refresh_dashboard_stats(account_id)

    return {"url": workspace.dashboard_url, "page_id": workspace.dashboard_page_id}


def publish_report(
    goal: GoalDefinition,
    onboarding: OnboardingData,
    account_id: str,
    diagnosis: MaturityDiagnosis | None = None,
    roadmap: RoadmapResult | None = None,
    parent_page_id: str | None = None,
    research: ResearchContext | None = None,
) -> dict:
    """기능 2(진단) + 기능 4(로드맵)를 함께 발행한다.

    대시보드는 이제 Opportunity Map/Roadmap 데이터베이스 중심이라, 진단 결과는 아직 이 대시보드에
    끼워 넣지 않는다(옵션이스 — SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절 오픈 이슈). roadmap이
    없으면 발행할 것이 없어 에러를 낸다(진단 전용 페이지는 이번 재설계 범위 밖).
    """
    if roadmap is None:
        raise ValueError("roadmap 없이는 발행할 대상이 없습니다 — 새 대시보드는 로드맵 데이터베이스 중심입니다.")

    return publish_roadmap(goal, roadmap, onboarding, account_id, parent_page_id, research)
