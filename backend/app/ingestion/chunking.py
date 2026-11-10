"""取り出したテキストを、検索の単位（チャンク）に分ける。

見出し（「第18条」「3.2」など）ごとに分け、長すぎる部分は文字数で分ける。
見出しをチャンクに残すことで、回答の根拠に「3.2 氏名変更」のように表示できる。
"""

import re
import unicodedata
from dataclasses import dataclass

from .extract import TextBlock

# 1チャンクの最大文字数。条文1つがほぼ収まり、かつ検索結果が長くなりすぎない長さにしている
MAX_CHUNK_CHARS = 800
# 長い部分を分けるときに前のチャンクと重ねる文字数。文の途中で切れても意味が分かるようにする
CHUNK_OVERLAP_CHARS = 100
# 見出しとみなす行の最大文字数。番号で始まる長い行は、箇条書きの本文であることが多いため
MAX_HEADING_CHARS = 40

_KANJI_NUMBER = "0-9〇一二三四五六七八九十百千"
_HEADING_PATTERNS = [
    re.compile(rf"^第[{_KANJI_NUMBER}]+[編章節款]"),  # 第3章 休暇
    re.compile(rf"^第[{_KANJI_NUMBER}]+条"),  # 第18条（育児休業）
    re.compile(r"^#{1,6}\s+\S"),  # Markdown の見出し
    # 番号の後に空白を必須にし、「2026.4.1から施行」のような本文を見出しにしない
    re.compile(r"^\d+(\.\d+)+\.?\s+\S"),  # 3.2 氏名変更
    re.compile(r"^\d+[.)]\s+\S"),  # 3. 届出の方法
    re.compile(r"^[【■◆●□].+"),  # 【申請の方法】
]
# 文の区切りになりやすい文字。長い部分を分けるとき、なるべくここで切る
_SENTENCE_ENDINGS = ("。", "\n", "．", "!", "?", "！", "？")


@dataclass
class Chunk:
    """検索の単位になる資料の断片。

    Attributes:
        content: 本文。先頭の部分には見出しの行も含む。
        section: 属する見出し。見出しより前の部分は None。
        page: 先頭の行のページ番号。
    """

    content: str
    section: str | None
    page: int | None


@dataclass
class _Section:
    heading: str | None
    lines: list[str]
    page: int | None
    has_body: bool = False


def normalize_text(text: str) -> str:
    """全角英数字を半角にするなど、表記の揺れをそろえる（見出しの判定に使う）。

    PDF から取り出した文字は全角・半角が混ざりやすく、「第１８条」が見出しと判定できないため。
    保存する本文は元の表記のままにする（「（」が「(」になると、画面での見え方が変わるため）。
    """
    return unicodedata.normalize("NFKC", _clean_spaces(text))


def _clean_spaces(text: str) -> str:
    return re.sub(r"[ \t　]+", " ", text).strip()


def is_heading(text: str) -> bool:
    """行が見出しの書き方になっているか判定する。

    Args:
        text: 1行のテキスト。

    Returns:
        見出しなら True。
    """
    text = normalize_text(text)
    if len(text) > MAX_HEADING_CHARS:
        return False
    return any(pattern.match(text) for pattern in _HEADING_PATTERNS)


def split_into_chunks(blocks: list[TextBlock]) -> list[Chunk]:
    """テキストを見出しと文字数でチャンクに分ける。

    Args:
        blocks: extract_text() で取り出した行・段落。

    Returns:
        資料の中の順番に並んだチャンク。本文がなければ空のリスト。
    """
    chunks: list[Chunk] = []
    for section in _group_by_heading(blocks):
        if not section.has_body:
            continue
        text = "\n".join(section.lines)
        for part in _split_long_text(text):
            chunks.append(Chunk(content=part, section=section.heading, page=section.page))
    return chunks


def _group_by_heading(blocks: list[TextBlock]) -> list[_Section]:
    sections: list[_Section] = []
    current = _Section(heading=None, lines=[], page=None)

    for block in blocks:
        text = _clean_spaces(block.text)
        if not text:
            continue
        heading = block.is_heading if block.is_heading is not None else is_heading(text)

        if heading:
            label = text.lstrip("#").strip()[:200]
            if current.has_body:
                sections.append(current)
                current = _Section(heading=label, lines=[text], page=block.page)
            else:
                # 「第3章 休暇」の直後に「第18条」が続くような、本文のない見出しは
                # 次の見出しとまとめる。
                # チャンクの見出しには、より細かい方（後の方）を使う
                current.heading = label
                current.lines.append(text)
                current.page = current.page or block.page
            continue

        current.lines.append(text)
        current.has_body = True
        current.page = current.page or block.page

    sections.append(current)
    return sections


def _split_long_text(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = start + MAX_CHUNK_CHARS
        if end >= len(text):
            parts.append(text[start:])
            break
        # 後半に文の区切りがあればそこで切る。なければ文字数で切る
        cut = max(text.rfind(mark, start + MAX_CHUNK_CHARS // 2, end) for mark in _SENTENCE_ENDINGS)
        if cut != -1:
            end = cut + 1
        parts.append(text[start:end].strip())
        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)
    return [part for part in parts if part]
