"""資料の管理（管理者・部署担当者）と、利用者の資料の閲覧の API。"""

import io
import json
import logging

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func, or_, select

from ..ai.retrieval import can_view
from ..auth import current_user, handles, login_required, roles_required
from ..extensions import db
from ..ingestion.registration import RegistrationError, register_document
from ..masters import DEPARTMENTS, DOCUMENT_CATEGORIES
from ..models import Document, DocumentChunk
from ..storage import get_storage
from .helpers import BadRequest, departments_target, error, parse_date, string_list

bp = Blueprint("documents", __name__)
log = logging.getLogger(__name__)

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


@bp.errorhandler(BadRequest)
def _bad_request(e: BadRequest):
    return error(str(e), 400)


def _chunk_counts(document_ids: list[int]) -> dict[int, int]:
    return dict(
        db.session.execute(
            select(DocumentChunk.document_id, func.count())
            .where(DocumentChunk.document_id.in_(document_ids))
            .group_by(DocumentChunk.document_id)
        ).all()
    )


def _to_dicts(documents: list[Document]) -> list[dict]:
    counts = _chunk_counts([d.id for d in documents])
    return [d.to_dict(counts.get(d.id, 0)) for d in documents]


def _managed_document(document_id: int) -> Document | None:
    """自分が管理できる資料。部署担当者は担当部署の資料だけ、管理者はすべて。"""
    document = db.session.get(Document, document_id)
    if document is None or not handles(current_user(), document.department):
        return None
    return document


@bp.get("/admin/documents")
@roles_required("staff", "admin")
def list_documents():
    user = current_user()
    query = select(Document).order_by(Document.updated_at.desc())
    if user.role != "admin":
        query = query.where(Document.department == user.handles_department)
    for key, column in [
        ("category", Document.category),
        ("department", Document.department),
        ("status", Document.status),
    ]:
        if value := request.args.get(key):
            query = query.where(column == value)
    if keyword := request.args.get("q", "").strip():
        pattern = f"%{keyword}%"
        query = query.where(or_(Document.title.ilike(pattern), Document.tags.contains([keyword])))
    return jsonify(_to_dicts(list(db.session.scalars(query))))


@bp.get("/admin/documents/<int:document_id>")
@roles_required("staff", "admin")
def get_document(document_id: int):
    document = _managed_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    count = _chunk_counts([document.id]).get(document.id, 0)
    return jsonify(document.to_dict(count, with_versions=True))


def _validate_meta(meta: dict, partial: bool = False) -> dict:
    """資料の情報（分類・部署・公開範囲・タグなど）を確かめる。

    Args:
        meta: 画面から送られた値。
        partial: PATCH のときは、送られた項目だけを確かめる。
    """
    values: dict = {}
    if "title" in meta and meta["title"] is not None:
        title = str(meta["title"]).strip()
        if not title or len(title) > 200:
            raise BadRequest("資料名は 1〜200 文字で入力してください")
        values["title"] = title
    if not partial or "category" in meta:
        if meta.get("category") not in DOCUMENT_CATEGORIES:
            raise BadRequest("分類を選択してください")
        values["category"] = meta["category"]
    if not partial or "department" in meta:
        department = meta.get("department")
        if department not in DEPARTMENTS:
            raise BadRequest("管理部署を選択してください")
        if not handles(current_user(), department):
            raise BadRequest("担当部署以外の資料は登録・変更できません")
        values["department"] = department
    if not partial or "visibility" in meta:
        visible = departments_target(meta.get("visibility"), "公開範囲")
        values["visibility_type"] = "departments" if visible else "all"
        values["visible_departments"] = visible
    if not partial or "tags" in meta:
        values["tags"] = string_list(meta.get("tags"), "タグ")
    return values


@bp.post("/admin/documents")
@roles_required("staff", "admin")
def upload_document():
    """資料をアップロードし、取り込み待ちにする（取り込みは worker が行う）。"""
    file = request.files.get("file")
    if file is None or not file.filename:
        raise BadRequest("ファイルを選択してください")
    try:
        meta = json.loads(request.form.get("meta") or "{}")
    except json.JSONDecodeError as e:
        raise BadRequest("資料の情報の形式が正しくありません") from e
    if not isinstance(meta, dict):
        raise BadRequest("資料の情報の形式が正しくありません")
    values = _validate_meta(meta)
    try:
        document = register_document(
            file.filename,
            file.read(),
            title=values.get("title") or file.filename.rsplit(".", 1)[0],
            department=values["department"],
            category=values["category"],
            visibility_type=values["visibility_type"],
            visible_departments=values["visible_departments"],
            tags=values["tags"],
            effective_date=parse_date(meta.get("effectiveDate")),
            uploaded_by=current_user(),
        )
    except RegistrationError as e:
        raise BadRequest(str(e)) from e
    return jsonify(document.to_dict()), 201


@bp.patch("/admin/documents/<int:document_id>")
@roles_required("staff", "admin")
def update_document(document_id: int):
    """資料名・分類・部署・公開範囲・タグを変える（再取り込みは不要）。"""
    document = _managed_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest("変更する内容の形式が正しくありません")
    for key, value in _validate_meta(body, partial=True).items():
        setattr(document, key, value)
    db.session.commit()
    count = _chunk_counts([document.id]).get(document.id, 0)
    return jsonify(document.to_dict(count))


@bp.post("/admin/documents/<int:document_id>/reindex")
@roles_required("staff", "admin")
def reindex_document(document_id: int):
    """取り込みに失敗した資料などを、もう一度取り込み待ちにする。"""
    document = _managed_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    if document.status == "processing":
        # 取り込み中に取り込み待ちへ戻すと、別の worker が同じ資料を二重に取り込むため
        return error("取り込み中の資料は、取り込みが終わってから取り込み直してください", 409)
    document.status = "processing"
    document.processing_stage = "uploaded"
    document.processing_started_at = None
    document.processing_attempts = 0
    document.error_message = None
    db.session.commit()
    return jsonify(document.to_dict(_chunk_counts([document.id]).get(document.id, 0)))


@bp.delete("/admin/documents/<int:document_id>")
@roles_required("staff", "admin")
def delete_document(document_id: int):
    """資料を削除する。すべての版の原本も削除する。"""
    document = _managed_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    keys = [version.storage_key for version in document.versions]
    db.session.delete(document)
    db.session.commit()
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            # 資料は削除済みなので、原本が消せなくても画面にはエラーにしない（ログで後から消す）
            log.exception("document %s: 原本 %s を削除できませんでした", document_id, key)
    return "", 204


def _viewable_document(document_id: int) -> Document | None:
    document = db.session.get(Document, document_id)
    if document is None or not can_view(document, current_user()):
        return None
    return document


@bp.get("/documents/<int:document_id>")
@login_required
def get_source(document_id: int):
    """回答の根拠資料の情報。閲覧できない資料は存在しないものとして扱う（ルール 7）。"""
    document = _viewable_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    return jsonify(document.to_dict(_chunk_counts([document.id]).get(document.id, 0)))


@bp.get("/documents/<int:document_id>/file")
@login_required
def get_file(document_id: int):
    """原本のファイル（最新の版）を返す。"""
    document = _viewable_document(document_id)
    if document is None:
        return error("資料が見つかりません", 404)
    version = document.latest_version
    data = get_storage().load(version.storage_key)
    return send_file(
        io.BytesIO(data),
        mimetype=MIME_TYPES.get(version.file_type, "application/octet-stream"),
        download_name=version.file_name,
        as_attachment=False,
    )
