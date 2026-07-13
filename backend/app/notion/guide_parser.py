"""
notion/guide_parser.py

task.detailed_guide(자유 텍스트)를 Notion 블록으로 바꾼다. Gemini가 항상 "1. "만 쓰는 건 아니라서
("1단계", "2번째" 등도 나옴) 줄바꿈이 아니라 숫자 마커가 나오는 위치 자체를 기준으로 텍스트를 쪼갠다.
"""

import re

from app.notion.rich_text import numbered, paragraph, quote

_STEP_MARKER = r"\d+\s*(?:[.)]|단계[:.]?|번째)\s*"
_STEP_SPLIT_RE = re.compile(rf"(?={_STEP_MARKER})")
_LEADING_NUMBER_RE = re.compile(rf"^{_STEP_MARKER}(.*)", re.DOTALL)


def render_guide_blocks(guide_text: str) -> list[dict]:
    blocks: list[dict] = []
    for raw_segment in _STEP_SPLIT_RE.split(guide_text):
        segment = raw_segment.strip()
        if not segment:
            continue
        match = _LEADING_NUMBER_RE.match(segment)
        if match:
            blocks.append(numbered(match.group(1).strip()))
        elif segment.startswith('"') and segment.endswith('"') and len(segment) > 1:
            blocks.append(quote(segment.strip('"')))
        else:
            blocks.append(paragraph(segment))
    return blocks or [paragraph("상세 가이드가 아직 준비되지 않았어요.")]
