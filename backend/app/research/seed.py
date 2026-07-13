"""큐레이션 seed findings 로더 (계약 v0.4 §2.6).

웹/검색에 안 나오는 사람이 정리한 소수 근거(예: 메일로 받은 사내 리포트)를
`fixtures/seed_findings_{goal_id}.json`에서 읽어 실시간 결과와 함께 병합한다.
파일이 없으면 빈 리스트(정상). finding_id는 service가 전체 순서에 맞춰 재부여하므로
seed 파일에는 넣지 않는다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_seed_findings(goal_id: str) -> list[dict]:
    """seed finding 내용(dict) 리스트. finding_id 제외한 Finding 필드들."""
    path = _FIXTURES / f"seed_findings_{goal_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("seed findings 로드 실패: %s", path)
        return []
    return data if isinstance(data, list) else []
