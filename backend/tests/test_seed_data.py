"""ダミー資料（seed/documents）と評価用の質問セット（evaluation/questions.json）の整合性。

資料を書き換えたときに、質問セットの正解の見出しが存在しなくなるのを防ぐ。
"""

import json
from functools import cache
from pathlib import Path

import pytest

from app.ingestion.chunking import split_into_chunks
from app.ingestion.extract import ExtractionError, extract_text, file_type_from_name

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BACKEND_DIR / "seed" / "documents"
MANIFEST = json.loads((SEED_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
QUESTIONS = json.loads((BACKEND_DIR / "evaluation" / "questions.json").read_text(encoding="utf-8"))[
    "questions"
]
DOCUMENTS_BY_TITLE = {entry["title"]: entry for entry in MANIFEST}


@cache
def _sections(slug: str) -> frozenset[str]:
    (path,) = (SEED_DIR / "files").glob(f"{slug}.*")
    blocks = extract_text(path.read_bytes(), file_type_from_name(path.name)).blocks
    return frozenset(chunk.section for chunk in split_into_chunks(blocks) if chunk.section)


@pytest.mark.parametrize("entry", MANIFEST, ids=lambda e: e["slug"])
def test_seed_file_can_be_ingested(entry):
    (path,) = (SEED_DIR / "files").glob(f"{entry['slug']}.*")
    if entry["format"] == "pdf_scanned":
        # 取り込みに失敗する例として、文字を含まない PDF にしている
        with pytest.raises(ExtractionError):
            extract_text(path.read_bytes(), "pdf")
        return
    assert len(_sections(entry["slug"])) >= 5


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_expected_sources_exist(question):
    for source in question["expectedSources"]:
        entry = DOCUMENTS_BY_TITLE[source["title"]]
        assert source["section"] in _sections(entry["slug"]), source


@pytest.mark.parametrize(
    "question", [q for q in QUESTIONS if q["type"] != "restricted"], ids=lambda q: q["id"]
)
def test_questioner_can_read_expected_sources(question):
    for source in question["expectedSources"]:
        visible = DOCUMENTS_BY_TITLE[source["title"]]["visibleDepartments"]
        assert visible is None or question["user"]["department"] in visible, source


def test_question_ids_are_unique():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
