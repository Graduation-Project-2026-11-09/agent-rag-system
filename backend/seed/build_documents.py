"""ダミー資料（seed/documents/source/*.md）から、PDF・Word・テキストのファイルを作る。

資料の取り込みを、実際のアップロードに近い形式で確かめるために使う。
作ったファイルは seed/documents/files/ に保存し、Git に含める（seed-documents で登録する）。

reportlab は PDF を作るときだけ必要なので、本番の依存パッケージには入れず、次のように実行する:

    docker compose run --rm --no-deps api \
        uv run --with reportlab==5.1.0 python seed/build_documents.py
"""

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

SEED_DIR = Path(__file__).resolve().parent / "documents"
SOURCE_DIR = SEED_DIR / "source"
OUTPUT_DIR = SEED_DIR / "files"
EXTENSIONS = {"pdf": "pdf", "pdf_scanned": "pdf", "docx": "docx", "txt": "txt", "md": "md"}
# 作り直すたびにファイルの中身が変わらないよう、作成日時を固定する
FIXED_TIME = datetime(2026, 1, 1)


@dataclass
class Block:
    """Markdown の1つの要素。

    Attributes:
        kind: title / h1 / h2 / paragraph / bullet / number / table。
        text: 本文（table 以外）。
        rows: 表のセル（table のみ）。
    """

    kind: str
    text: str = ""
    rows: list[list[str]] = field(default_factory=list)


def parse_markdown(source: str) -> list[Block]:
    """このスクリプトで使う範囲の Markdown（見出し・箇条書き・表）を読み取る。"""
    blocks: list[Block] = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            if blocks and blocks[-1].kind == "table":
                blocks[-1].rows.append(cells)
            else:
                blocks.append(Block(kind="table", rows=[cells]))
            continue
        if line.startswith("### "):
            blocks.append(Block(kind="h2", text=line[4:]))
        elif line.startswith("## "):
            blocks.append(Block(kind="h1", text=line[3:]))
        elif line.startswith("# "):
            blocks.append(Block(kind="title", text=line[2:]))
        elif line.startswith("- "):
            blocks.append(Block(kind="bullet", text=line[2:]))
        elif re.match(r"^\d+\. ", line):
            blocks.append(Block(kind="number", text=line))
        else:
            blocks.append(Block(kind="paragraph", text=line))
    return blocks


def write_txt(blocks: list[Block], path: Path) -> None:
    # 見出しの記号がない、普通のテキストの資料を想定する（見出しは書き方から判定される）
    lines: list[str] = []
    for block in blocks:
        if block.kind in ("title", "h1"):
            lines += ["", block.text, ""]
        elif block.kind == "h2":
            lines += ["", block.text]
        elif block.kind == "bullet":
            lines.append(f"・{block.text}")
        elif block.kind == "table":
            lines += ["　".join(row) for row in block.rows]
        else:
            lines.append(block.text)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_docx(blocks: list[Block], path: Path) -> None:
    from docx import Document

    document = Document()
    document.core_properties.created = FIXED_TIME
    document.core_properties.modified = FIXED_TIME
    styles = {"title": "Title", "h1": "Heading 1", "h2": "Heading 2"}
    for block in blocks:
        if block.kind in styles:
            document.add_paragraph(block.text, style=styles[block.kind])
        elif block.kind == "bullet":
            document.add_paragraph(block.text, style="List Bullet")
        elif block.kind == "number":
            document.add_paragraph(re.sub(r"^\d+\. ", "", block.text), style="List Number")
        elif block.kind == "table":
            table = document.add_table(rows=len(block.rows), cols=len(block.rows[0]))
            table.style = "Table Grid"
            for row, cells in zip(table.rows, block.rows, strict=True):
                for cell, text in zip(row.cells, cells, strict=False):
                    cell.text = text
        else:
            document.add_paragraph(block.text)
    document.save(path)


def write_pdf(blocks: list[Block], path: Path) -> None:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rl_config.invariant = 1  # 作成日時などを固定し、作り直しても同じファイルにする
    for font in ("HeiseiKakuGo-W5", "HeiseiMin-W3"):
        pdfmetrics.registerFont(UnicodeCIDFont(font))

    def style(name: str, font: str, size: float, space: float) -> ParagraphStyle:
        return ParagraphStyle(
            name,
            fontName=font,
            fontSize=size,
            leading=size * 1.6,
            spaceBefore=space,
            spaceAfter=space / 2,
            wordWrap="CJK",
        )

    styles = {
        "title": style("title", "HeiseiKakuGo-W5", 18, 6),
        "h1": style("h1", "HeiseiKakuGo-W5", 13, 10),
        "h2": style("h2", "HeiseiKakuGo-W5", 11, 6),
        "paragraph": style("body", "HeiseiMin-W3", 10, 1),
        "cell": style("cell", "HeiseiMin-W3", 9, 0),
    }
    story = []
    for block in blocks:
        if block.kind == "table":
            data = [[Paragraph(escape(c), styles["cell"]) for c in row] for row in block.rows]
            table = Table(data, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story += [table, Spacer(1, 4 * mm)]
            continue
        text = f"・{block.text}" if block.kind == "bullet" else block.text
        story.append(Paragraph(escape(text), styles.get(block.kind, styles["paragraph"])))

    def draw_page_number(canvas, doc) -> None:
        canvas.setFont("HeiseiMin-W3", 8)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"- {doc.page} -")

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=blocks[0].text,
    )
    doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)


def write_scanned_pdf(path: Path) -> None:
    """スキャンした紙の資料を想定し、文字を含まない（線だけの）PDF を作る。"""
    from reportlab import rl_config
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    rl_config.invariant = 1
    pdf = canvas.Canvas(str(path), pagesize=A4)
    for page in range(2):
        pdf.setFillGray(0.95)
        pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        pdf.setFillGray(0.35)
        y = A4[1] - 80
        for line in range(38 if page == 0 else 20):
            # 行の長さを少しずつ変え、文字の行のように見せる
            width = 420 - (line * 37 % 140)
            pdf.rect(70, y, width, 6, fill=1, stroke=0)
            y -= 18
        pdf.showPage()
    pdf.save()


def main() -> None:
    manifest = json.loads((SEED_DIR / "manifest.json").read_text(encoding="utf-8"))
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for entry in manifest["documents"]:
        source_path = SOURCE_DIR / f"{entry['slug']}.md"
        output = OUTPUT_DIR / f"{entry['slug']}.{EXTENSIONS[entry['format']]}"
        blocks = parse_markdown(source_path.read_text(encoding="utf-8"))
        match entry["format"]:
            case "md":
                shutil.copyfile(source_path, output)
            case "txt":
                write_txt(blocks, output)
            case "docx":
                write_docx(blocks, output)
            case "pdf":
                write_pdf(blocks, output)
            case "pdf_scanned":
                write_scanned_pdf(output)
        print(f"{output.name}: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
