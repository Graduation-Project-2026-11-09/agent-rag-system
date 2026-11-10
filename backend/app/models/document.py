"""社内資料と、検索に使うチャンクのモデル。"""

from datetime import date, datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

# text-embedding-3-large の次元数。DB のカラム定義と一致させる必要があるため、
# 環境変数では変えられないようにしている（変えるときはマイグレーションが必要）
EMBEDDING_DIMENSIONS = 3072

VISIBILITY_TYPES = ("all", "departments")
STATUSES = ("processing", "indexed", "error")
# processing 中の段階。画面が約 0.7 秒ごとに取得して進み具合を表示する（docs/api-spec.md）
PROCESSING_STAGES = ("uploaded", "extracting", "chunking", "embedding")


class Document(db.Model):
    """社内資料。版（DocumentVersion）をまとめたもので、公開範囲を持つ。

    Attributes:
        visibility_type: all（全員）/ departments（visible_departments の部署だけ）。
        visible_departments: visibility_type が departments のときに閲覧できる部署。
        status: processing（取り込み中）/ indexed（検索可能）/ error（取り込み失敗）。
        processing_stage: processing 中の段階。processing 以外は None。
        processing_started_at: worker が取り込みを始めた日時。止まった処理の検知に使う。
        processing_attempts: 今回の取り込みを始めた回数。worker が途中で止まって
            取り込み直すたびに増え、上限を超えたら error にする。
        current_version: 最新の版の番号。
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            f"visibility_type IN {VISIBILITY_TYPES}", name="ck_documents_visibility_type"
        ),
        CheckConstraint(f"status IN {STATUSES}", name="ck_documents_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    visibility_type: Mapped[str] = mapped_column(String(16), default="all")
    visible_departments: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    status: Mapped[str] = mapped_column(String(16), default="processing", index=True)
    processing_stage: Mapped[str | None] = mapped_column(String(16))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", order_by="DocumentVersion.version"
    )

    @property
    def latest_version(self) -> "DocumentVersion":
        """取り込みの対象になる最新の版。"""
        return next(v for v in self.versions if v.version == self.current_version)


class DocumentVersion(db.Model):
    """資料の1つの版。原本ファイルの情報を持つ。

    改定したときは新しい版を追加し、古い版は履歴として残す。

    Attributes:
        storage_key: 原本の保存先のキー（S3 のキー、または開発環境のファイルパス）。
        pages: ページ数。PDF 以外は None。
    """

    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    effective_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")


class DocumentChunk(db.Model):
    """検索の単位になる資料の断片と、そのベクトル。

    検索できるのは最新の版のチャンクだけ。取り込みが終わると古い版のチャンクは削除する。

    Attributes:
        section: チャンクが属する見出し（例: 「第18条（育児休業）」）。根拠の表示に使う。
        page: 先頭の行があるページ番号。ページの概念がない形式は None。
        embedding: text-embedding-3-large のベクトル。3072 次元は vector 型では
            HNSW 索引の上限（2000 次元）を超えるため、半精度の halfvec 型で保存する。
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(HALFVEC(EMBEDDING_DIMENSIONS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
