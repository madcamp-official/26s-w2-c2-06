from app.notion.guide_parser import render_guide_blocks


def test_splits_newline_separated_numbered_steps():
    blocks = render_guide_blocks("1. 첫 단계\n2. 둘째 단계\n3. 셋째 단계")
    numbered_texts = [b["numbered_list_item"]["rich_text"][0]["text"]["content"] for b in blocks]
    assert numbered_texts == ["첫 단계", "둘째 단계", "셋째 단계"]


def test_splits_steps_even_without_newlines():
    guide = "1. IT팀에 라이선스를 요청합니다. 2. copilot.microsoft.com에 로그인합니다. 3. 새 채팅창을 엽니다."
    blocks = render_guide_blocks(guide)
    numbered_texts = [b["numbered_list_item"]["rich_text"][0]["text"]["content"] for b in blocks]
    assert len(numbered_texts) == 3
    assert "IT팀에 라이선스를 요청합니다." in numbered_texts[0]
    assert "copilot.microsoft.com에 로그인합니다." in numbered_texts[1]
    assert "새 채팅창을 엽니다." in numbered_texts[2]


def test_splits_steps_written_as_dangye_or_beonjjae():
    guide = "1단계: 라이선스를 요청합니다.\n2번째 로그인합니다."
    blocks = render_guide_blocks(guide)
    numbered_texts = [b["numbered_list_item"]["rich_text"][0]["text"]["content"] for b in blocks]
    assert len(numbered_texts) == 2
    assert "라이선스를 요청합니다." in numbered_texts[0]
    assert "로그인합니다." in numbered_texts[1]


def test_numbered_step_can_contain_quoted_prompt_inline():
    guide = '1. 로그인한다\n2. 채팅창에 "이 문서를 3줄로 요약해줘"라고 입력한다'
    blocks = render_guide_blocks(guide)
    numbered_texts = [b["numbered_list_item"]["rich_text"][0]["text"]["content"] for b in blocks]
    assert any("이 문서를 3줄로 요약해줘" in t for t in numbered_texts)


def test_renders_standalone_quote_when_no_number_precedes_it():
    blocks = render_guide_blocks('"참고만 하고 실제 문구는 상황에 맞게 바꿔서 쓰세요"')
    quote_texts = [b["quote"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "quote"]
    assert "참고만 하고 실제 문구는 상황에 맞게 바꿔서 쓰세요" in quote_texts


def test_falls_back_to_placeholder_when_empty():
    blocks = render_guide_blocks("")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
