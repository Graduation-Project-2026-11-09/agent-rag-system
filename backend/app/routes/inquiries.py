"""担当部署への問い合わせの API。"""

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..auth import current_user, handles, login_required, roles_required
from ..extensions import db
from ..masters import DEPARTMENTS
from ..models import Inquiry, InquiryReply, Message
from ..models.inquiry import STATUSES
from .helpers import (
    BadRequest,
    error,
    is_ascii_digits,
    json_body,
    optional_text,
    parse_id,
    required_text,
    string_list,
)

bp = Blueprint("inquiries", __name__)


@bp.errorhandler(BadRequest)
def _bad_request(e: BadRequest):
    return error(str(e), 400)


def _query():
    return (
        select(Inquiry).options(selectinload(Inquiry.replies)).order_by(Inquiry.created_at.desc())
    )


@bp.get("/inquiries/mine")
@login_required
def list_mine():
    """自分が送った問い合わせ（回答を含む）。"""
    inquiries = db.session.scalars(_query().where(Inquiry.user_id == current_user().id))
    return jsonify([i.to_dict() for i in inquiries])


@bp.post("/inquiries")
@login_required
def create():
    """問い合わせを送る。

    利用者が確認画面で「承認して送信」を押したときだけ呼ばれる
    （AI が自動で送ることはない。CLAUDE.md のルール 5）。
    """
    user = current_user()
    data = json_body()
    department = str(data.get("department") or "")
    if department not in DEPARTMENTS:
        raise BadRequest("問い合わせ先の部署を選択してください")
    context = data.get("context") if isinstance(data.get("context"), dict) else {}

    message = None
    if data.get("messageId"):
        # 「承認して送信」が連打されても同じ回答から 2 件作らないよう、行をロックしてから確かめる
        message = db.session.get(
            Message, parse_id(data["messageId"], "元の回答"), with_for_update=True
        )
        if (
            message is None
            or message.role != "assistant"
            or message.conversation.user_id != user.id
        ):
            return error("元の回答が見つかりません", 404)
        if message.inquiry_id is not None:
            return error("この回答からはすでに問い合わせを送信しています", 409)

    inquiry = Inquiry(
        user_id=user.id,
        user_name=user.name,
        user_department=user.department,
        department=department,
        subject=required_text(data, "subject", "件名", 200),
        body=required_text(data, "body", "本文", 10000),
        status="open",
        context={
            "question": str(context.get("question") or ""),
            "sources": string_list(context.get("sources"), "確認済みの資料"),
            "aiAnswerSummary": str(context.get("aiAnswerSummary") or ""),
        },
    )
    db.session.add(inquiry)
    db.session.flush()
    if message is not None:
        message.inquiry_id = inquiry.id  # 利用履歴で「問い合わせ」として数える
    db.session.commit()
    return jsonify(inquiry.to_dict()), 201


@bp.get("/admin/inquiries")
@roles_required("staff", "admin")
def list_for_staff():
    """担当部署あての問い合わせ。管理者はすべての部署。"""
    user = current_user()
    query = _query()
    if user.role != "admin":
        query = query.where(Inquiry.department == user.handles_department)
    if status := request.args.get("status"):
        query = query.where(Inquiry.status == status)
    if department := request.args.get("department"):
        query = query.where(Inquiry.department == department)
    if keyword := request.args.get("q", "").strip():
        conditions = [
            Inquiry.subject.ilike(f"%{keyword}%"),
            Inquiry.user_name.ilike(f"%{keyword}%"),
        ]
        # 問い合わせ番号（INQ-2026-0142）でも探せるようにする。番号の最後は id
        number = keyword.rsplit("-", 1)[-1]
        if is_ascii_digits(number):
            conditions.append(Inquiry.id == int(number))
        query = query.where(or_(*conditions))
    return jsonify([i.to_dict() for i in db.session.scalars(query)])


def _handled_inquiry(inquiry_id: int) -> Inquiry | None:
    inquiry = db.session.get(Inquiry, inquiry_id)
    if inquiry is None or not handles(current_user(), inquiry.department):
        return None
    return inquiry


@bp.get("/admin/inquiries/<int:inquiry_id>")
@roles_required("staff", "admin")
def get(inquiry_id: int):
    inquiry = _handled_inquiry(inquiry_id)
    if inquiry is None:
        return error("問い合わせが見つかりません", 404)
    return jsonify(inquiry.to_dict())


@bp.patch("/admin/inquiries/<int:inquiry_id>")
@roles_required("staff", "admin")
def update(inquiry_id: int):
    """対応状況と担当者を変える。"""
    inquiry = _handled_inquiry(inquiry_id)
    if inquiry is None:
        return error("問い合わせが見つかりません", 404)
    data = json_body()
    if "status" in data:
        if data["status"] not in STATUSES:
            raise BadRequest("対応状況の値が正しくありません")
        inquiry.status = data["status"]
    if "assignee" in data:
        inquiry.assignee = optional_text(data, "assignee", "担当者", 100)
    db.session.commit()
    return jsonify(inquiry.to_dict())


@bp.post("/admin/inquiries/<int:inquiry_id>/replies")
@roles_required("staff", "admin")
def reply(inquiry_id: int):
    """問い合わせに回答する。未対応なら対応中にし、担当者が未設定なら回答した人にする。"""
    inquiry = _handled_inquiry(inquiry_id)
    if inquiry is None:
        return error("問い合わせが見つかりません", 404)
    user = current_user()
    body = required_text(json_body(), "body", "回答", 10000)
    inquiry.replies.append(
        InquiryReply(author_id=user.id, author_name=user.name, author_role=user.role, body=body)
    )
    if inquiry.status == "open":
        inquiry.status = "in_progress"
    if not inquiry.assignee:
        inquiry.assignee = user.name
    db.session.commit()
    return jsonify(inquiry.to_dict()), 201
