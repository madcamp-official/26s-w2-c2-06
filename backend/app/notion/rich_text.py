"""Notion 블록 JSON을 만드는 최소 단위 함수들. blocks.py/guide_parser.py가 공유한다."""


def text(content: str) -> dict:
    return {"type": "text", "text": {"content": content}}


def bold_text(content: str) -> dict:
    return {"type": "text", "text": {"content": content}, "annotations": {"bold": True}}


def link_text(content: str, url: str) -> dict:
    return {"type": "text", "text": {"content": content, "link": {"url": url}}}


def paragraph(content: str) -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": [text(content)]}}


def labeled_paragraph(label: str, content: str) -> dict:
    """굵은 라벨 + 일반 텍스트로 된 한 줄. 예: **기대 효과:** 검색 시간 감소"""
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [bold_text(f"{label}: "), text(content)]},
    }


def divider() -> dict:
    return {"type": "divider", "divider": {}}


def table_of_contents() -> dict:
    return {"type": "table_of_contents", "table_of_contents": {}}


def toggle(summary: str, children: list[dict]) -> dict:
    return {"type": "toggle", "toggle": {"rich_text": [text(summary)], "children": children}}


def checkable(label: str, children: list[dict], checked: bool = False) -> dict:
    """체크박스(to_do) + 중첩 내용. Notion에서 체크박스와 펼치기 화살표가 함께 보인다."""
    return {
        "type": "to_do",
        "to_do": {"rich_text": [text(label)], "checked": checked, "children": children},
    }


def columns(*column_children: list[dict]) -> dict:
    """블록들을 좌우로 나란히 배치한다. columns([a, b], [c]) -> 2단 컬럼, 왼쪽엔 a,b / 오른쪽엔 c."""
    return {
        "type": "column_list",
        "column_list": {
            "children": [{"type": "column", "column": {"children": children}} for children in column_children]
        },
    }


def heading2(content: str) -> dict:
    return {"type": "heading_2", "heading_2": {"rich_text": [text(content)]}}


def heading3(content: str) -> dict:
    return {"type": "heading_3", "heading_3": {"rich_text": [text(content)]}}


def callout(content: str, icon: str = "💡", color: str | None = None) -> dict:
    block = {"type": "callout", "callout": {"rich_text": [text(content)], "icon": {"emoji": icon}}}
    if color:
        block["callout"]["color"] = color
    return block


def bulleted(content: str) -> dict:
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [text(content)]}}


def bulleted_rich(spans: list[dict]) -> dict:
    """이미 만든 rich_text span들(예: link_text + text 조합)로 글머리 기호 항목을 만든다."""
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": spans}}


def numbered(content: str) -> dict:
    return {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [text(content)]}}


def quote(content: str) -> dict:
    return {"type": "quote", "quote": {"rich_text": [text(content)]}}
