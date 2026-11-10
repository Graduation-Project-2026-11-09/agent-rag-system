"""利用者が閲覧できる資料の中から、検索語に近いチャンクを探す。"""

from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from sqlalchemy import ColumnElement, or_, select, text, true

from ..extensions import db
from ..models import Document, DocumentChunk, DocumentVersion, User
from .embedding import embed_texts
from .llm import Usage

# 1 つの検索語で取り出すチャンクの数
HITS_PER_QUERY = 5
# 回答の材料にするチャンクの最大数。多いほど見落としは減るが、入力が長くなり費用が増える
MAX_HITS = 10
# これより類似度が低いチャンクは関係がないとみなす（評価の結果を見て調整する）
MIN_SCORE = 0.25


@dataclass(frozen=True)
class Viewer:
    """検索する利用者の情報。

    AI の応答を待つ間に DB のトランザクションを開かないよう、
    ORM の User ではなく必要な値だけを持たせる
    （User の属性を読むと、DB に問い合わせてトランザクションが始まることがあるため）。
    """

    id: int
    name: str
    department: str
    role: str

    @classmethod
    def from_user(cls, user: User) -> "Viewer":
        return cls(id=user.id, name=user.name, department=user.department, role=user.role)


@dataclass
class SearchHit:
    """検索で見つかったチャンク。

    Attributes:
        score: 検索語との類似度（コサイン類似度。1 に近いほど似ている）。
    """

    chunk_id: int
    document_id: int
    title: str
    file_type: str
    department: str
    updated_at: datetime
    section: str | None
    page: int | None
    content: str
    score: float

    def to_step_result(self) -> dict:
        """検索の過程として画面に表示する形にする。"""
        return {
            "documentId": str(self.document_id),
            "title": self.title,
            "section": self.section,
            "score": round(self.score, 2),
        }


def visible_to(user: User | Viewer) -> ColumnElement[bool]:
    """利用者が閲覧できる資料に絞り込む条件を返す（CLAUDE.md のルール 7）。

    管理者はすべての資料を、それ以外は全員向けの資料と、所属部署向けの資料を閲覧できる。
    """
    if user.role == "admin":
        return true()
    return or_(
        Document.visibility_type == "all",
        Document.visible_departments.contains([user.department]),
    )


def can_view(document: Document, user: User | Viewer) -> bool:
    """利用者が資料を閲覧できるか判定する。visible_to() と同じ基準。"""
    if user.role == "admin" or document.visibility_type == "all":
        return True
    return user.department in document.visible_departments


def count_visible_documents(user: User | Viewer) -> int:
    """利用者が検索できる（取り込み済みの）資料の数。検索の過程の表示に使う。"""
    return db.session.scalar(
        select(db.func.count(Document.id)).where(Document.status == "indexed", visible_to(user))
    )


def search_chunks(queries: list[str], user: Viewer, usage: Usage) -> list[SearchHit]:
    """検索語ごとにベクトル検索し、まとめて類似度の高い順に返す。

    公開範囲の絞り込みは検索の中で行う。検索した後に絞り込むと、
    閲覧できるチャンクが件数の上限より少なくなってしまうため。

    Args:
        queries: 検索語。
        user: 質問した利用者。
        usage: 埋め込みで使ったトークン数を加える先。

    Returns:
        類似度の高い順のチャンク（最大 MAX_HITS 件）。該当がなければ空のリスト。

    Raises:
        EmbeddingError: 検索語のベクトル化に失敗した場合。
    """
    if not queries:
        return []
    embedded = embed_texts(queries)
    usage.add(current_app.config["AI_EMBEDDING_MODEL"], embedded.total_tokens, 0)

    # HNSW 索引で絞り込みを使うと、条件に合う行が上限より少なく返ることがあるため、
    # 足りない分を索引の続きから探させる（pgvector 0.8 以降）
    db.session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

    best: dict[int, SearchHit] = {}
    for vector in embedded.vectors:
        distance = DocumentChunk.embedding.cosine_distance(vector)
        rows = db.session.execute(
            select(DocumentChunk, Document, DocumentVersion.file_type, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
            .where(visible_to(user))
            .order_by(distance)
            .limit(HITS_PER_QUERY)
        ).all()
        for chunk, document, file_type, chunk_distance in rows:
            score = 1 - float(chunk_distance)
            if score < MIN_SCORE:
                continue
            if chunk.id not in best or best[chunk.id].score < score:
                best[chunk.id] = SearchHit(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    title=document.title,
                    file_type=file_type,
                    department=document.department,
                    updated_at=document.updated_at,
                    section=chunk.section,
                    page=chunk.page,
                    content=chunk.content,
                    score=score,
                )
    # このあと AI の応答を待つ間にトランザクションを開いたままにしないよう、ここで閉じる
    db.session.rollback()
    return sorted(best.values(), key=lambda hit: hit.score, reverse=True)[:MAX_HITS]
