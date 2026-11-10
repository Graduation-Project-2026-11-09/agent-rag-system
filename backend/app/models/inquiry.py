"""担当部署への問い合わせのモデル。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

STATUSES = ("open", "in_progress", "resolved")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class Inquiry(db.Model):
    """利用者が AI のチャットから担当部署に送った問い合わせ。

    AI は下書きを作るだけで、送信（このテーブルへの登録）は利用者が承認したときだけ行う。

    Attributes:
        user_name: 送信時の氏名。アカウントが削除されても問い合わせの記録を残すため写しておく。
        assignee: 対応している担当者の氏名。
        context: 元の質問・確認済みの資料・AI の回答の要約。
    """

    __tablename__ = "inquiries"
    __table_args__ = (CheckConstraint(f"status IN {STATUSES}", name="ck_inquiries_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    user_name: Mapped[str] = mapped_column(String(100))
    user_department: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    assignee: Mapped[str | None] = mapped_column(String(100))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    replies: Mapped[list["InquiryReply"]] = relationship(
        back_populates="inquiry", order_by="InquiryReply.id", cascade="all, delete-orphan"
    )

    @property
    def number(self) -> str:
        """画面に表示する問い合わせ番号（例: INQ-2026-0142）。"""
        year = self.created_at.year if self.created_at else datetime.now().year
        return f"INQ-{year}-{self.id:04d}"

    def to_dict(self) -> dict:
        """API のレスポンス形式（docs/api-spec.md の Inquiry）に変換する。"""
        return {
            "id": str(self.id),
            "number": self.number,
            "userId": str(self.user_id) if self.user_id else None,
            "userName": self.user_name,
            "userDepartment": self.user_department,
            "department": self.department,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "assignee": self.assignee,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
            "context": self.context or {},
            "replies": [reply.to_dict() for reply in self.replies],
        }


class InquiryReply(db.Model):
    """問い合わせへの担当部署からの回答。"""

    __tablename__ = "inquiry_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_name: Mapped[str] = mapped_column(String(100))
    author_role: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    inquiry: Mapped[Inquiry] = relationship(back_populates="replies")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "author": self.author_name,
            "authorRole": self.author_role,
            "body": self.body,
            "createdAt": _iso(self.created_at),
        }
