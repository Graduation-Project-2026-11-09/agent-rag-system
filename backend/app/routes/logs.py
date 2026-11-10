"""利用履歴（管理者）と、マスタの API。"""

from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import Select, or_, select

from ..auth import login_required, roles_required
from ..extensions import db
from ..masters import DEPARTMENTS, DOCUMENT_CATEGORIES
from ..models import Conversation, Message, User
from .helpers import BadRequest, error, is_ascii_digits

bp = Blueprint("logs", __name__)


@bp.errorhandler(BadRequest)
def _bad_request(e: BadRequest):
    return error(str(e), 400)


# 企画書の試算: 自己解決 1 件あたり 20 分の対応時間を減らせる
SAVED_MINUTES_PER_RESOLVED = 20


@bp.get("/departments")
@login_required
def departments():
    return jsonify(list(DEPARTMENTS))


@bp.get("/document-categories")
@login_required
def document_categories():
    return jsonify(list(DOCUMENT_CATEGORIES))


def _log_query(days: str | None) -> Select:
    """AI の回答（= 1 件の利用）を、質問した利用者と一緒に取り出す。"""
    query = (
        select(Message, User)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .where(Message.role == "assistant")
        .order_by(Message.created_at.desc())
    )
    if days:
        # 不正な値を黙って無視すると、全期間が返って集計を誤るため 400 にする
        if not is_ascii_digits(days) or int(days) == 0:
            raise BadRequest("期間の指定が正しくありません")
        query = query.where(Message.created_at >= datetime.now(UTC) - timedelta(days=int(days)))
    return query


def _to_log(message: Message, user: User) -> dict:
    """docs/api-spec.md の Log の形にする。費用の確認のため、トークン数と費用も加える。"""
    return {
        "id": str(message.id),
        "at": message.created_at.isoformat(),
        "userId": str(user.id),
        "userName": user.name,
        "department": user.department,
        "question": message.question or "",
        "messageId": str(message.id),
        "searchCount": message.search_count or 0,
        "sourceCount": len(message.sources or []),
        "result": message.result,
        "feedback": message.feedback,
        "durationMs": message.duration_ms or 0,
        "steps": message.steps or [],
        "sources": [
            f"{s['title']} {s.get('section') or ''}".strip() for s in message.sources or []
        ],
        "mode": message.mode,
        "inputTokens": message.input_tokens,
        "outputTokens": message.output_tokens,
        "costUsd": message.cost_usd,
    }


@bp.get("/admin/logs")
@roles_required("admin")
def list_logs():
    query = _log_query(request.args.get("days"))
    if department := request.args.get("department"):
        query = query.where(User.department == department)
    if keyword := request.args.get("q", "").strip():
        pattern = f"%{keyword}%"
        query = query.where(or_(Message.question.ilike(pattern), User.name.ilike(pattern)))
    logs = [_to_log(m, u) for m, u in db.session.execute(query).all()]
    # result は問い合わせの有無などから決まる値なので、SQL ではなくここで絞り込む
    if result := request.args.get("result"):
        logs = [log for log in logs if log["result"] == result]
    return jsonify(logs)


@bp.get("/admin/logs/summary")
@roles_required("admin")
def summary():
    logs = [_to_log(m, u) for m, u in db.session.execute(_log_query(request.args.get("days")))]
    total = len(logs)
    resolved = sum(1 for log in logs if log["result"] == "resolved")
    rated = [log for log in logs if log["feedback"]]
    costs = [log["costUsd"] for log in logs if log["costUsd"] is not None]
    return jsonify(
        total=total,
        resolvedRate=resolved / total if total else 0,
        inquiryCount=sum(1 for log in logs if log["result"] == "inquiry"),
        avgSearchCount=sum(log["searchCount"] for log in logs) / total if total else 0,
        avgDurationMs=sum(log["durationMs"] for log in logs) / total if total else 0,
        goodRate=sum(1 for log in rated if log["feedback"] == "good") / len(rated) if rated else 0,
        savedMinutes=resolved * SAVED_MINUTES_PER_RESOLVED,
        totalCostUsd=sum(costs),
    )
