from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai.embedding import EmbeddingError, EmbeddingResult
from app.extensions import db
from app.ingestion import pipeline
from app.ingestion.pipeline import UNEXPECTED_ERROR_MESSAGE, ingest_next
from app.ingestion.registration import RegistrationError, register_document
from app.models import Document, DocumentChunk
from app.models.document import EMBEDDING_DIMENSIONS
from app.storage import get_storage

# ダミーの資料（本物の社内資料は使わない）
SAMPLE_TEXT = """休暇規程（ダミー）
第1条（目的）
この規程は、従業員の休暇について定める。
第2条（結婚休暇）
本人が結婚するときは、5日の特別休暇を与える。
""".encode()


@pytest.fixture
def fake_embed(monkeypatch):
    """OpenAI API を呼ばずに、固定のベクトルを返す。"""
    calls: list[list[str]] = []

    def embed(texts):
        calls.append(texts)
        return EmbeddingResult(
            vectors=[[0.01 * (i + 1)] * EMBEDDING_DIMENSIONS for i in range(len(texts))],
            total_tokens=10 * len(texts),
        )

    monkeypatch.setattr(pipeline, "embed_texts", embed)
    return calls


def _register(**kwargs) -> Document:
    return register_document(
        "kyuka_kitei.txt",
        SAMPLE_TEXT,
        title=kwargs.pop("title", "休暇規程"),
        department="人事部",
        **kwargs,
    )


def test_register_document_saves_file_and_waits_for_worker(app):
    document = _register()

    assert document.status == "processing"
    assert document.processing_stage == "uploaded"
    version = document.latest_version
    assert version.file_type == "txt"
    assert version.size == len(SAMPLE_TEXT)
    # 原本はファイル名ではなく、ランダムな名前で保存する
    assert "kyuka" not in version.storage_key
    assert get_storage().load(version.storage_key) == SAMPLE_TEXT


def test_register_rejects_invalid_input(app):
    with pytest.raises(RegistrationError, match="対応していない形式"):
        register_document("a.xlsx", b"x", title="t", department="人事部")
    with pytest.raises(RegistrationError, match="空"):
        register_document("a.txt", b"", title="t", department="人事部")
    with pytest.raises(RegistrationError, match="部署を1つ以上"):
        _register(visibility_type="departments")


def test_register_department_only_document(app):
    document = _register(visibility_type="departments", visible_departments=["人事部", "総務部"])
    assert document.visible_departments == ["人事部", "総務部"]


def test_ingest_next_creates_chunks(app, fake_embed):
    document_id = _register().id

    assert ingest_next() is True

    db.session.expire_all()  # DB に保存された値を読み直す
    document = db.session.get(Document, document_id)
    assert document.status == "indexed"
    assert document.processing_stage is None
    chunks = db.session.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index)).all()
    assert [c.section for c in chunks] == [None, "第1条（目的）", "第2条（結婚休暇）"]
    assert len(chunks[0].embedding) == EMBEDDING_DIMENSIONS
    # 資料名と見出しを付けてからベクトルにする
    assert fake_embed[0][2].startswith("休暇規程\n第2条（結婚休暇）\n")

    assert ingest_next() is False


def test_reindex_replaces_old_chunks(app, fake_embed):
    document_id = _register().id
    ingest_next()

    document = db.session.get(Document, document_id)
    document.status = "processing"
    document.processing_stage = "uploaded"
    db.session.commit()
    ingest_next()

    assert len(db.session.scalars(select(DocumentChunk)).all()) == 3


def test_embedding_error_marks_document_as_error(app, monkeypatch):
    def fail(texts):
        raise EmbeddingError("ベクトル化に失敗しました（APITimeoutError）")

    monkeypatch.setattr(pipeline, "embed_texts", fail)
    document_id = _register().id

    assert ingest_next() is True

    document = db.session.get(Document, document_id)
    assert document.status == "error"
    assert "ベクトル化に失敗" in document.error_message
    assert db.session.scalars(select(DocumentChunk)).all() == []


def test_unexpected_error_hides_details(app, monkeypatch):
    def fail(texts):
        raise RuntimeError("内部の詳細")

    monkeypatch.setattr(pipeline, "embed_texts", fail)
    document_id = _register().id
    ingest_next()

    assert db.session.get(Document, document_id).error_message == UNEXPECTED_ERROR_MESSAGE


def test_unreadable_file_is_error(app, fake_embed):
    document_id = register_document(
        "scan.pdf", b"%PDF-broken", title="スキャン", department="総務部"
    ).id
    ingest_next()

    document = db.session.get(Document, document_id)
    assert document.status == "error"
    assert "読み取れませんでした" in document.error_message
    assert fake_embed == []


def test_stale_processing_is_retried(app, fake_embed):
    document_id = _register().id
    document = db.session.get(Document, document_id)
    # worker が途中で止まり、embedding の段階のまま残った状態
    document.processing_stage = "embedding"
    document.processing_started_at = datetime.now(UTC) - timedelta(hours=1)
    db.session.commit()

    assert ingest_next() is True
    assert db.session.get(Document, document_id).status == "indexed"


def test_in_progress_document_is_not_claimed_twice(app, fake_embed):
    document_id = _register().id
    document = db.session.get(Document, document_id)
    # 別の worker が処理中
    document.processing_stage = "embedding"
    document.processing_started_at = datetime.now(UTC)
    db.session.commit()

    assert ingest_next() is False


def test_import_document_command(app, tmp_path, fake_embed):
    path = tmp_path / "結婚の手続き.md"
    path.write_text("# 結婚したとき\n氏名変更届を出す。\n", encoding="utf-8")

    result = app.test_cli_runner().invoke(
        args=["import-document", str(path), "--department", "人事部", "--tag", "結婚"]
    )

    assert result.exit_code == 0, result.output
    document = db.session.scalar(select(Document))
    assert document.title == "結婚の手続き"
    assert document.visibility_type == "all"
    assert document.tags == ["結婚"]


def test_import_document_command_rejects_unsupported_file(app, tmp_path):
    path = tmp_path / "budget.xlsx"
    path.write_bytes(b"x")

    result = app.test_cli_runner().invoke(
        args=["import-document", str(path), "--department", "経理部"]
    )

    assert result.exit_code != 0
    assert "対応していない形式" in result.output


def test_register_rejects_values_longer_than_columns(app):
    with pytest.raises(RegistrationError, match="資料名は 200 文字以内"):
        _register(title="あ" * 201)
    with pytest.raises(RegistrationError, match="ファイル名は 255 文字以内"):
        register_document("a" * 252 + ".txt", b"x", title="t", department="人事部")
    with pytest.raises(RegistrationError, match="タグは 50 文字以内"):
        _register(tags=["あ" * 51])
    with pytest.raises(RegistrationError, match="部署は 100 文字以内"):
        register_document("a.txt", b"x", title="t", department="部" * 101)
    assert db.session.scalars(select(Document)).all() == []


def test_register_removes_file_when_commit_fails(app, monkeypatch):
    saved = []
    storage = get_storage()
    monkeypatch.setattr("app.ingestion.registration.get_storage", lambda: storage)
    original_save = storage.save
    monkeypatch.setattr(
        storage, "save", lambda key, data: (saved.append(key), original_save(key, data))
    )

    def fail():
        raise RuntimeError("DB に接続できません")

    monkeypatch.setattr(db.session, "commit", fail)
    with pytest.raises(RuntimeError):
        _register()

    with pytest.raises(FileNotFoundError):
        storage.load(saved[0])


def test_stalled_document_gives_up_after_max_attempts(app, fake_embed):
    document_id = _register().id
    document = db.session.get(Document, document_id)
    # 取り込み中に worker が止まることが、上限の回数続いた状態
    document.processing_stage = "embedding"
    document.processing_started_at = datetime.now(UTC) - timedelta(hours=1)
    document.processing_attempts = pipeline.MAX_ATTEMPTS
    db.session.commit()

    assert ingest_next() is False

    document = db.session.get(Document, document_id)
    assert document.status == "error"
    assert document.error_message == pipeline.TOO_MANY_ATTEMPTS_MESSAGE
    assert document.processing_attempts == 0  # 取り込み直すときは 1 回目から数える
    assert fake_embed == []


def test_attempts_are_counted_and_reset_after_success(app, fake_embed):
    document_id = _register().id
    ingest_next()
    assert db.session.get(Document, document_id).processing_attempts == 0


def test_seed_documents_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-documents"])

    assert result.exit_code == 0, result.output
    documents = db.session.scalars(select(Document)).all()
    assert len(documents) == 23
    hyoka = next(d for d in documents if d.title.startswith("人事評価"))
    assert hyoka.visibility_type == "departments"
    assert hyoka.visible_departments == ["人事部"]
    assert {d.latest_version.file_type for d in documents} == {"pdf", "docx", "txt", "md"}

    # 2 回目は登録済みの資料を飛ばす
    result = runner.invoke(args=["seed-documents"])
    assert "0 件登録しました" in result.output
