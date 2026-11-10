"""worker が行う資料の取り込み（テキスト抽出 → チャンク分割 → ベクトル化 → 保存）。"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update

from ..ai.client import AIConfigError
from ..ai.embedding import EmbeddingError, embed_texts
from ..extensions import db
from ..models import Document, DocumentChunk, DocumentVersion
from ..storage import get_storage
from .chunking import Chunk, split_into_chunks
from .extract import ExtractionError, extract_text

log = logging.getLogger(__name__)

# worker が途中で止まった（再起動など）資料を、この時間が過ぎたら取り込み直す
STALE_AFTER = timedelta(minutes=30)
UNEXPECTED_ERROR_MESSAGE = "取り込み中に予期しないエラーが発生しました。取り込み直してください"


@dataclass
class _Job:
    """取り込む資料の情報。

    DB のトランザクションを開いたまま OpenAI API を待つと、
    idle_in_transaction_session_timeout（60 秒）で接続が切られるため、
    必要な値を先に取り出してから重い処理をする。
    """

    document_id: int
    version_id: int
    version: int
    title: str
    storage_key: str
    file_type: str


def ingest_next() -> bool:
    """取り込み待ちの資料を1件取り込む。

    Returns:
        資料を1件処理したら True（成功・失敗を問わない）。取り込み待ちがなければ False。
    """
    job = _claim_next_job()
    if job is None:
        return False

    try:
        _process(job)
    except (ExtractionError, EmbeddingError, AIConfigError) as e:
        db.session.rollback()
        log.warning("document %s: 取り込みに失敗しました: %s", job.document_id, e)
        _mark_error(job, str(e))
    except Exception:
        db.session.rollback()
        log.exception("document %s: 取り込み中に予期しないエラー", job.document_id)
        _mark_error(job, UNEXPECTED_ERROR_MESSAGE)
    return True


def _claim_next_job() -> _Job | None:
    stale_before = datetime.now(UTC) - STALE_AFTER
    # worker が複数あっても同じ資料を二重に処理しないよう、ロック中の行は飛ばす
    document = db.session.scalar(
        select(Document)
        .where(
            Document.status == "processing",
            or_(
                Document.processing_stage == "uploaded",
                Document.processing_started_at < stale_before,
            ),
        )
        .order_by(Document.updated_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if document is None:
        db.session.rollback()
        return None

    version = document.latest_version
    job = _Job(
        document_id=document.id,
        version_id=version.id,
        version=version.version,
        title=document.title,
        storage_key=version.storage_key,
        file_type=version.file_type,
    )
    document.processing_stage = "extracting"
    document.processing_started_at = datetime.now(UTC)
    document.error_message = None
    db.session.commit()
    return job


def _process(job: _Job) -> None:
    data = get_storage().load(job.storage_key)
    extracted = extract_text(data, job.file_type)
    db.session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.id == job.version_id)
        .values(pages=extracted.pages)
    )
    _set_stage(job, "chunking")

    chunks = split_into_chunks(extracted.blocks)
    if not chunks:
        raise ExtractionError("本文が見つかりませんでした")
    _set_stage(job, "embedding")

    result = embed_texts([_embedding_input(job.title, chunk) for chunk in chunks])
    log.info(
        "document %s: %d 件のチャンクを取り込みました（%d トークン）",
        job.document_id,
        len(chunks),
        result.total_tokens,
    )
    _save_chunks(job, chunks, result.vectors)


def _embedding_input(title: str, chunk: Chunk) -> str:
    # 「第18条」だけでは何の資料か分からないため、資料名と見出しを付けてからベクトルにする
    header = f"{title}\n{chunk.section}" if chunk.section else title
    return f"{header}\n{chunk.content}"


def _set_stage(job: _Job, stage: str) -> None:
    db.session.execute(
        update(Document)
        .where(Document.id == job.document_id, Document.current_version == job.version)
        .values(processing_stage=stage)
    )
    db.session.commit()


def _save_chunks(job: _Job, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    document = db.session.get(Document, job.document_id, with_for_update=True)
    if document is None or document.current_version != job.version:
        # 取り込み中に資料が削除された、または新しい版が登録された。新しい版は次に処理する
        db.session.rollback()
        log.info("document %s: 版が変わったため、取り込み結果を保存しません", job.document_id)
        return

    # 古い版のチャンクは検索に使わないため削除する（版の情報と原本は履歴として残る）
    db.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == job.document_id))
    db.session.add_all(
        DocumentChunk(
            document_id=job.document_id,
            document_version_id=job.version_id,
            chunk_index=index,
            section=chunk.section,
            page=chunk.page,
            content=chunk.content,
            embedding=vector,
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    )
    document.status = "indexed"
    document.processing_stage = None
    document.processing_started_at = None
    document.error_message = None
    db.session.commit()


def _mark_error(job: _Job, message: str) -> None:
    db.session.execute(
        update(Document)
        .where(Document.id == job.document_id, Document.current_version == job.version)
        .values(
            status="error",
            processing_stage=None,
            processing_started_at=None,
            error_message=message,
        )
    )
    db.session.commit()
