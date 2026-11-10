"""チャットの会話とメッセージのモデル。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

FEEDBACKS = ("good", "bad")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class Conversation(db.Model):
    """利用者ごとのチャットの会話。"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", cascade="all, delete-orphan"
    )

    def to_dict(self, with_messages: bool = False) -> dict:
        """API のレスポンス形式（docs/api-spec.md の Conversation）に変換する。"""
        data = {
            "id": str(self.id),
            "userId": str(self.user_id),
            "title": self.title,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }
        if with_messages:
            data["messages"] = [message.to_dict() for message in self.messages]
        return data


class Message(db.Model):
    """会話の 1 つの発言。AI の回答には、処理の過程・根拠資料・使ったトークン数も保存する。

    利用履歴（管理者の画面）は、このテーブルの AI の回答から作る。

    Attributes:
        role: user（利用者の質問）/ assistant（AI の回答）。
        question: AI の回答のもとになった質問。利用履歴の表示に使う。
        steps: 処理の過程（SSE の step と同じ形）。
        answer_status: answered / partial / not_found。
        mode: agentic（検索Agent）/ basic（通常の RAG）。
        inquiry_id: この回答から送信した問い合わせ。
        cost_usd: OpenAI API の費用の目安。
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list | None] = mapped_column(JSONB)
    search_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[list | None] = mapped_column(JSONB)
    next_steps: Mapped[list | None] = mapped_column(JSONB)
    inquiry_suggestion: Mapped[dict | None] = mapped_column(JSONB)
    inquiry_id: Mapped[int | None] = mapped_column(Integer, index=True)
    answer_status: Mapped[str | None] = mapped_column(String(16))
    mode: Mapped[str | None] = mapped_column(String(16))
    feedback: Mapped[str | None] = mapped_column(String(8))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    @property
    def result(self) -> str:
        """利用履歴の結果。resolved（自己解決）/ inquiry（問い合わせ）/ no_answer（回答不可）。"""
        if self.inquiry_id is not None:
            return "inquiry"
        if self.answer_status in ("not_found", "partial"):
            return "no_answer"
        return "resolved"

    def to_dict(self) -> dict:
        """API のレスポンス形式（docs/api-spec.md の Message）に変換する。"""
        data = {
            "id": str(self.id),
            "role": self.role,
            "content": self.content,
            "createdAt": _iso(self.created_at),
        }
        if self.role == "user":
            return data
        data.update(
            {
                "agent": {
                    "steps": self.steps or [],
                    "searchCount": self.search_count or 0,
                    "durationMs": self.duration_ms or 0,
                },
                "sources": self.sources or [],
                "nextSteps": self.next_steps or [],
                "inquirySuggestion": self.inquiry_suggestion,
                "inquiryId": str(self.inquiry_id) if self.inquiry_id else None,
                "feedback": self.feedback,
            }
        )
        return data
