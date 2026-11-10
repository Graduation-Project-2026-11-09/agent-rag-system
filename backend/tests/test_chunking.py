from app.ingestion.chunking import (
    CHUNK_OVERLAP_CHARS,
    MAX_CHUNK_CHARS,
    is_heading,
    normalize_text,
    split_into_chunks,
)
from app.ingestion.extract import TextBlock


def _blocks(*lines: str, page: int | None = None) -> list[TextBlock]:
    return [TextBlock(text=line, page=page) for line in lines]


def test_split_by_article_headings():
    chunks = split_into_chunks(
        _blocks(
            "第1条（目的）",
            "この規程は、休暇について定める。",
            "第2条（結婚休暇）",
            "本人が結婚するときは、5日の休暇を与える。",
        )
    )

    assert [c.section for c in chunks] == ["第1条（目的）", "第2条（結婚休暇）"]
    # 見出しの行も本文に残し、検索結果だけで何の条文か分かるようにする
    assert chunks[1].content == "第2条（結婚休暇）\n本人が結婚するときは、5日の休暇を与える。"


def test_heading_without_body_is_merged_into_next_section():
    chunks = split_into_chunks(
        _blocks("第3章 休暇", "第18条（育児休業）", "子が1歳になるまで休業できる。")
    )

    assert len(chunks) == 1
    assert chunks[0].section == "第18条（育児休業）"
    assert chunks[0].content.startswith("第3章 休暇\n第18条（育児休業）")


def test_text_before_first_heading_has_no_section():
    chunks = split_into_chunks(_blocks("人事手続きマニュアル", "1. 氏名変更", "届出をする。"))

    assert chunks[0].section is None
    assert chunks[0].content == "人事手続きマニュアル"
    assert chunks[1].section == "1. 氏名変更"


def test_long_section_is_split_with_overlap():
    sentence = "結婚した場合は、人事システムから氏名変更届を提出する。"
    body = sentence * 60  # 約 1,600 字
    chunks = split_into_chunks(_blocks("3.2 氏名変更", body))

    assert len(chunks) >= 2
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    assert all(c.section == "3.2 氏名変更" for c in chunks)
    # 文の区切りで切れていて、次のチャンクの先頭は前のチャンクの末尾と重なる
    assert chunks[0].content.endswith("。")
    assert chunks[0].content[-CHUNK_OVERLAP_CHARS // 2 :] in chunks[1].content


def test_page_is_first_line_of_section():
    blocks = [
        TextBlock(text="第1条（目的）", page=3),
        TextBlock(text="本文", page=3),
        TextBlock(text="続き", page=4),
    ]
    assert split_into_chunks(blocks)[0].page == 3


def test_explicit_heading_flag_overrides_pattern():
    blocks = [
        TextBlock(text="申請の方法", is_heading=True),
        TextBlock(text="1. 申請書を出す", is_heading=False),
    ]
    chunks = split_into_chunks(blocks)
    assert len(chunks) == 1
    assert chunks[0].section == "申請の方法"


def test_normalize_text_unifies_width_and_spaces():
    assert normalize_text("第１８条　（育児休業）") == "第18条 (育児休業)"


def test_is_heading():
    assert is_heading("第18条 (育児休業)")
    assert is_heading("第3章 休暇")
    assert is_heading("3.2 氏名変更")
    assert is_heading("## 申請の方法")
    assert is_heading("【提出先】")
    # 日付や長い本文は見出しにしない
    assert not is_heading("2026.4.1から施行する。")
    assert not is_heading("1. " + "長い本文" * 20)
    assert not is_heading("本人が結婚するときは休暇を与える。")


def test_empty_blocks():
    assert split_into_chunks([]) == []
    assert split_into_chunks(_blocks("第1条")) == []
