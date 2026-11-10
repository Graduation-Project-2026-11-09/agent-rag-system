"""資料のファイルからテキストを取り出す。"""

import io
import re
from dataclasses import dataclass, field

# 対応する形式（拡張子 → file_type）。Excel・PowerPoint は後で対応する（docs/architecture/ai.md）
SUPPORTED_EXTENSIONS = {
    "pdf": "pdf",
    "docx": "docx",
    "txt": "txt",
    "md": "md",
}


class ExtractionError(Exception):
    """テキストを取り出せなかった。メッセージは資料管理画面にそのまま表示する。"""


@dataclass
class TextBlock:
    """資料の1行（または1段落）。

    Attributes:
        text: 本文。
        page: ページ番号（1 始まり）。ページの概念がない形式は None。
        is_heading: 形式から見出しと分かる場合は True。分からない場合は None
            （チャンク分割のときに書き方から判定する）。
    """

    text: str
    page: int | None = None
    is_heading: bool | None = None


@dataclass
class ExtractedText:
    """ファイルから取り出したテキスト。

    Attributes:
        blocks: 本文の行・段落。資料の中の順番に並ぶ。
        pages: ページ数。PDF 以外は None。
    """

    blocks: list[TextBlock] = field(default_factory=list)
    pages: int | None = None


def file_type_from_name(file_name: str) -> str:
    """ファイル名の拡張子から file_type を決める。

    Args:
        file_name: アップロードされたファイル名。

    Returns:
        pdf / docx / txt / md のいずれか。

    Raises:
        ExtractionError: 対応していない形式の場合。
    """
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in SUPPORTED_EXTENSIONS:
        supported = "・".join(SUPPORTED_EXTENSIONS)
        raise ExtractionError(f"対応していない形式です（対応形式: {supported}）")
    return SUPPORTED_EXTENSIONS[extension]


def extract_text(data: bytes, file_type: str) -> ExtractedText:
    """ファイルの内容からテキストを取り出す。

    Args:
        data: ファイルの内容。
        file_type: file_type_from_name() で決めた形式。

    Returns:
        取り出したテキスト。

    Raises:
        ExtractionError: ファイルが壊れている、またはテキストが含まれていない場合。
    """
    extractors = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "txt": _extract_plain,
        "md": _extract_markdown,
    }
    try:
        result = extractors[file_type](data)
    except ExtractionError:
        raise
    except Exception as e:
        # 壊れたファイルではライブラリごとに様々な例外が出るため、まとめて利用者向けの理由にする
        raise ExtractionError(f"ファイルを読み取れませんでした（{type(e).__name__}）") from e

    if not any(block.text.strip() for block in result.blocks):
        message = "テキストを読み取れませんでした"
        if file_type == "pdf":
            message += "（画像だけの PDF の可能性があります）"
        raise ExtractionError(message)
    return result


def _extract_pdf(data: bytes) -> ExtractedText:
    """PDF を 1 行ずつ、ページ番号つきで取り出す。"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ExtractionError("パスワードが設定された PDF は読み取れません")

    result = ExtractedText(pages=len(reader.pages))
    for page_number, page in enumerate(reader.pages, start=1):
        for line in (page.extract_text() or "").splitlines():
            if line.strip():
                result.blocks.append(TextBlock(text=line, page=page_number))
    return result


def _extract_docx(data: bytes) -> ExtractedText:
    """Word を段落と表の行ごとに、見出しのスタイルつきで取り出す。"""
    from docx import Document
    from docx.table import Table

    result = ExtractedText()
    for item in Document(io.BytesIO(data)).iter_inner_content():
        if isinstance(item, Table):
            # 表は1行ずつ「セル | セル」の形にする。結合セルは同じ値が続くので重複を除く
            for row in item.rows:
                cells = list(dict.fromkeys(cell.text.strip() for cell in row.cells))
                text = " | ".join(c for c in cells if c)
                if text:
                    result.blocks.append(TextBlock(text=text, is_heading=False))
            continue

        text = item.text.strip()
        if not text:
            continue
        style_name = (item.style.name if item.style is not None else "") or ""
        if style_name.startswith(("Heading", "Title", "見出し", "表題")):
            is_heading = True
        elif style_name.startswith(("List", "リスト", "箇条書き")):
            # 「1. 申請書を出す」のような手順の番号を見出しと間違えないようにする
            is_heading = False
        else:
            # 見出しのスタイルを使っていない資料も多いため、その場合は書き方から判定させる
            is_heading = None
        result.blocks.append(TextBlock(text=text, is_heading=is_heading))
    return result


def _decode_text(data: bytes) -> str:
    """テキストファイルの文字コードを判定して文字列にする。"""
    # Windows で作られたテキストは Shift_JIS（cp932）のことがあるため、UTF-8 で読めなければ試す
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("文字コードを判定できませんでした（UTF-8 で保存してください）")


def _extract_plain(data: bytes) -> ExtractedText:
    """テキストを 1 行ずつ取り出す。見出しはチャンク分割のときに書き方から判定する。"""
    lines = _decode_text(data).splitlines()
    return ExtractedText(blocks=[TextBlock(text=line) for line in lines if line.strip()])


_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s")
_MARKDOWN_TABLE_RULE = re.compile(r"^\|?\s*:?-{3,}")


def _extract_markdown(data: bytes) -> ExtractedText:
    """Markdown を 1 行ずつ取り出し、「#」の行を見出しにする。"""
    # Markdown は「#」で見出しがはっきり分かるため、それ以外の行（「1. 」で始まる手順など）は
    # 見出しにしない
    blocks = []
    for line in _decode_text(data).splitlines():
        stripped = line.strip()
        if not stripped or _MARKDOWN_TABLE_RULE.match(stripped):
            continue  # 表の区切り行（| --- |）は内容がないため除く
        is_heading = bool(_MARKDOWN_HEADING.match(stripped))
        blocks.append(TextBlock(text=stripped, is_heading=is_heading))
    return ExtractedText(blocks=blocks)
