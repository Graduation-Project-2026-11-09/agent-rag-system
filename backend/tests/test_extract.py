import io

import pytest
from docx import Document

from app.ingestion.extract import ExtractionError, extract_text, file_type_from_name


def _build_pdf(pages: list[str]) -> bytes:
    """テキストだけの最小の PDF を作る（英数字のみ。標準フォントの Helvetica を使う）。"""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font_id = 3 + len(pages) * 2
    for i, text in enumerate(pages):
        content_id = 4 + i * 2
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET" if text else ""
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def test_file_type_from_name():
    assert file_type_from_name("就業規則.PDF") == "pdf"
    assert file_type_from_name("manual.docx") == "docx"
    with pytest.raises(ExtractionError, match="対応していない形式"):
        file_type_from_name("budget.xlsx")
    with pytest.raises(ExtractionError):
        file_type_from_name("README")


def test_extract_plain_text_utf8_and_cp932():
    text = "第1条（目的）\n\nこの規程は休暇について定める。\n"
    for encoding in ("utf-8", "cp932"):
        result = extract_text(text.encode(encoding), "txt")
        assert [b.text for b in result.blocks] == [
            "第1条（目的）",
            "この規程は休暇について定める。",
        ]
        assert result.pages is None


def test_extract_docx_headings_and_tables():
    document = Document()
    document.add_heading("申請の方法", level=1)
    document.add_paragraph("人事システムから申請する。")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "提出先"
    table.rows[0].cells[1].text = "人事部"
    buffer = io.BytesIO()
    document.save(buffer)

    blocks = extract_text(buffer.getvalue(), "docx").blocks

    assert [(b.text, b.is_heading) for b in blocks] == [
        ("申請の方法", True),
        ("人事システムから申請する。", None),
        ("提出先 | 人事部", False),
    ]


def test_extract_pdf_keeps_page_numbers():
    result = extract_text(_build_pdf(["Article 1 Purpose", "Article 2 Leave"]), "pdf")

    assert result.pages == 2
    assert [(b.text.strip(), b.page) for b in result.blocks] == [
        ("Article 1 Purpose", 1),
        ("Article 2 Leave", 2),
    ]


def test_pdf_without_text_is_error():
    with pytest.raises(ExtractionError, match="画像だけの PDF"):
        extract_text(_build_pdf([""]), "pdf")


def test_broken_file_is_error():
    with pytest.raises(ExtractionError, match="読み取れませんでした"):
        extract_text(b"not a docx", "docx")


def test_extract_markdown_uses_only_hash_headings():
    text = (
        "# 接続の手順\n1. アイコンをクリックする\n"
        "| 症状 | 対処 |\n| --- | --- |\n| 失敗 | 再接続 |\n"
    )
    blocks = extract_text(text.encode(), "md").blocks

    assert [(b.text, b.is_heading) for b in blocks] == [
        ("# 接続の手順", True),
        # 手順の番号は見出しにしない
        ("1. アイコンをクリックする", False),
        ("| 症状 | 対処 |", False),
        ("| 失敗 | 再接続 |", False),
    ]


def test_extract_docx_list_is_not_heading():
    document = Document()
    document.add_paragraph("申請書を出す", style="List Number")
    buffer = io.BytesIO()
    document.save(buffer)

    assert extract_text(buffer.getvalue(), "docx").blocks[0].is_heading is False
