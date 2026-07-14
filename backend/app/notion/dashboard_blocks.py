"""
notion/dashboard_blocks.py

"AX 대시보드" 페이지의 초기 블록. 콜아웃 2개(발견한 AI Opportunity 수 / AX 적용한 업무 수)만
먼저 만들어 페이지에 넣고, 그 뒤 팀원/Opportunity Map/Roadmap 데이터베이스를 이 페이지를
parent로 생성하면 Notion이 각 데이터베이스의 child_database 블록을 페이지 끝에 자동으로 붙여준다
(공개 API가 뷰를 직접 못 만드니 이 자동 부착 동작에 기댄다 — 9절 참고).

콜아웃은 항상 맨 앞 두 블록(인덱스 0, 1)이라 위치를 계산할 필요가 없다 — `sync.py`가 이 값을
그대로 가정하고 `get_block_children`으로 다시 조회해 블록 ID를 알아낸다.
"""

from app.notion.rich_text import callout, divider

DISCOVERED_COUNT_BLOCK_INDEX = 0
APPLIED_COUNT_BLOCK_INDEX = 1


def _stat_text(label: str, count: int) -> str:
    return f"{label}: {count}건 (새로고침 기준)"


def build_dashboard_blocks() -> list[dict]:
    return [
        callout(_stat_text("발견한 AI Opportunity 수", 0), icon="🔍"),
        callout(_stat_text("AX 적용한 업무 수", 0), icon="🚀"),
        divider(),
    ]
