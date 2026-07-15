"""
notion/dashboard_blocks.py

"AX 대시보드" 페이지의 최상단 블록. QA_amendments 2절에 따라 예전엔 여기 있던 콜아웃 2개
(발견한 AI Opportunity 수 / AX 적용한 업무 수, 수동 새로고침 필요)를 없애고, 대신 이번 목표
문장 하나만 보라색(purple_background) 콜아웃으로 보여준다. 집계 차트는 자동 발행 대상에서
아예 뺐다 — 이유는 sync.py 모듈 독스트링 참고(Notion "Dashboard" 뷰는 유료 플랜 전용, 대안인
평범한 chart 뷰는 원하는 위치에 놓을 수 없어 자동화를 포기하고 사용자가 `/linked`로 직접
만들도록 안내한다).

콜아웃은 항상 맨 앞 블록(인덱스 0)이라 위치를 계산할 필요가 없다 — sync.py가 이 값을 그대로
가정하고 `get_block_children`으로 다시 조회해 블록 ID를 알아내(goal_callout_block_id로 저장)
재발행마다 목표 문구를 최신으로 갱신한다.
"""

from app.notion.rich_text import callout, divider

GOAL_CALLOUT_BLOCK_INDEX = 0
GOAL_CALLOUT_COLOR = "purple_background"


def goal_callout_text(goal_text: str) -> str:
    return goal_text or "목표가 아직 설정되지 않았어요."


def build_dashboard_blocks(goal_text: str) -> list[dict]:
    return [
        callout(goal_callout_text(goal_text), icon="🎯", color=GOAL_CALLOUT_COLOR),
        divider(),
    ]
