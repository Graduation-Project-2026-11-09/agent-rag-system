"""チャット（会話・質問・回答の評価）の API。"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from sqlalchemy import select

from ..ai import agent
from ..ai.client import AIConfigError
from ..ai.embedding import EmbeddingError
from ..ai.llm import LLMError
from ..ai.retrieval import Viewer
from ..auth import current_user, login_required
from ..extensions import db
from ..models import Conversation, Message
from ..models.chat import FEEDBACKS

bp = Blueprint("chat", __name__)
log = logging.getLogger(__name__)

# 画面の会話一覧に表示するタイトルの長さ（モックと同じ）
TITLE_CHARS = 24
MAX_QUESTION_CHARS = 2000
GENERATION_ERROR = "回答の生成に失敗しました。時間をおいてもう一度お試しください"


def _own_conversation(conversation_id: int) -> Conversation | None:
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user().id:
        return None
    return conversation


@bp.get("/conversations")
@login_required
def list_conversations():
    """自分の会話の一覧（新しく更新された順）。"""
    conversations = db.session.scalars(
        select(Conversation)
        .where(Conversation.user_id == current_user().id)
        .order_by(Conversation.updated_at.desc())
    )
    return jsonify([c.to_dict() for c in conversations])


@bp.get("/conversations/<int:conversation_id>")
@login_required
def get_conversation(conversation_id: int):
    """会話をメッセージつきで返す。"""
    conversation = _own_conversation(conversation_id)
    if conversation is None:
        return jsonify(message="会話が見つかりません"), 404
    return jsonify(conversation.to_dict(with_messages=True))


@bp.post("/conversations")
@login_required
def create_conversation():
    """新しい会話を作る。"""
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip() or "新しい会話"
    conversation = Conversation(user_id=current_user().id, title=title[:TITLE_CHARS])
    db.session.add(conversation)
    db.session.commit()
    return jsonify(conversation.to_dict()), 201


@bp.delete("/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id: int):
    """会話を削除する。"""
    conversation = _own_conversation(conversation_id)
    if conversation is None:
        return jsonify(message="会話が見つかりません"), 404
    db.session.delete(conversation)
    db.session.commit()
    return "", 204


@bp.post("/conversations/<int:conversation_id>/messages")
@login_required
def send_message(conversation_id: int):
    """質問を受け付け、検索Agent の処理の過程と回答を SSE で送る。

    送るイベントは docs/api-spec.md「質問送信（Server-Sent Events）」のとおり。
    """
    conversation = _own_conversation(conversation_id)
    if conversation is None:
        return jsonify(message="会話が見つかりません"), 404
    data = request.get_json(silent=True) or {}
    content = str(data.get("content") or "").strip()
    if not content:
        return jsonify(message="質問を入力してください"), 400
    if len(content) > MAX_QUESTION_CHARS:
        return jsonify(message=f"質問は {MAX_QUESTION_CHARS} 文字以内で入力してください"), 400

    history = [agent.HistoryItem(role=m.role, content=m.content) for m in conversation.messages]
    db.session.add(Message(conversation_id=conversation.id, role="user", content=content))
    conversation.updated_at = datetime.now(UTC)
    db.session.commit()

    viewer = Viewer.from_user(current_user())
    mode = current_app.config["AI_RAG_MODE"]
    db.session.rollback()  # AI の応答を待つ間にトランザクションを開いたままにしない

    def stream() -> Iterator[str]:
        try:
            result = yield from _relay_steps(agent.run(content, viewer, history, mode))
        except (LLMError, EmbeddingError, AIConfigError):
            db.session.rollback()
            log.exception("conversation %s: 回答の生成に失敗しました", conversation_id)
            yield _event("error", {"message": GENERATION_ERROR})
            return

        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.content,
            question=content,
            steps=result.steps,
            search_count=result.search_count,
            duration_ms=result.duration_ms,
            sources=result.sources,
            next_steps=result.next_steps,
            inquiry_suggestion=result.inquiry_suggestion,
            answer_status=result.answer_status,
            mode=result.mode,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.usage.cost_usd,
        )
        db.session.add(message)
        db.session.get(Conversation, conversation_id).updated_at = datetime.now(UTC)
        db.session.commit()
        yield _event("answer", message.to_dict())

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        # 途中のプロキシに溜め込まれず、1 段階ずつ画面に届くようにする
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _relay_steps(steps) -> Iterator[str]:
    """エージェントの step を SSE のイベントにして流し、最後にエージェントの結果を返す。"""
    while True:
        try:
            step = next(steps)
        except StopIteration as finished:
            return finished.value
        yield _event("step", step)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@bp.post("/messages/<int:message_id>/feedback")
@login_required
def send_feedback(message_id: int):
    """AI の回答に評価（good / bad / 取り消し）を付ける。"""
    message = db.session.get(Message, message_id)
    if (
        message is None
        or message.role != "assistant"
        or message.conversation.user_id != current_user().id
    ):
        return jsonify(message="メッセージが見つかりません"), 404
    feedback = (request.get_json(silent=True) or {}).get("feedback")
    if feedback is not None and feedback not in FEEDBACKS:
        return jsonify(message="評価の値が正しくありません"), 400
    message.feedback = feedback
    db.session.commit()
    return "", 204
