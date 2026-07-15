"""
notion/dashboard_blocks.py

"AX 대시보드" 페이지의 초기 블록. 콜아웃 2개(발견한 AI Opportunity 수 / AX 적용한 업무 수)만
먼저 만들어 페이지에 넣고, 그 뒤 팀원/Opportunity Map/Roadmap 데이터베이스를 이 페이지를
parent로 생성하면 Notion이 각 데이터베이스의 child_database 블록을 페이지 끝에 자동으로 붙여준다
(공개 API가 뷰를 직접 못 만드니 이 자동 부착 동작에 기댄다 — 9절 참고). 데이터베이스는
`create_database`가 `is_inline: true`로 만들어서 이 블록이 링크 카드가 아니라 행이 바로 보이는
표로 붙는다.

콜아웃은 항상 맨 앞 두 블록(인덱스 0, 1)이라 위치를 계산할 필요가 없다 — `sync.py`가 이 값을
그대로 가정하고 `get_block_children`으로 다시 조회해 블록 ID를 알아낸다. goal_text는 그 뒤에
붙는 소개 문단이라 인덱스 계산에 영향 없음.
"""

from app.notion.rich_text import callout, divider, paragraph

DISCOVERED_COUNT_BLOCK_INDEX = 0
APPLIED_COUNT_BLOCK_INDEX = 1


def _stat_text(label: str, count: int) -> str:
    return f"{label}: {count}건 (새로고침 기준)"


def build_dashboard_blocks(goal_text: str = "") -> list[dict]:
    blocks = [
        callout(_stat_text("발견한 AI Opportunity 수", 0), icon="🔍"),
        callout(_stat_text("AX 적용한 업무 수", 0), icon="🚀"),
        divider(),
    ]
    if goal_text:
        blocks.append(
            paragraph(
                f'"{goal_text}"라는 목표로 만든 로드맵이에요. '
                "아래 데이터베이스에서 업무 전체 지도와 실행 계획을 확인하실 수 있어요."
            )
        )
    return blocks
