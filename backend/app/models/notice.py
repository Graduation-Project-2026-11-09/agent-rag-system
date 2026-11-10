"""お知らせと、管理者の設定のモデル。"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db

PRIORITIES = ("normal", "important")
CHANNELS = ("in_app", "email")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class Notice(db.Model):
    """管理者・部署担当者が配信するお知らせ。

    予約配信は、配信日時（publish_at）を過ぎたら表示するだけで実現する（定期的な処理は使わない）。
    メールでの配信は今は行わない（channels の email は保存だけする）。

    Attributes:
        target_departments: 配信先の部署。空なら全員。
        is_draft: 下書き。true の間は配信日時を過ぎても表示しない。
    """

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    target_departments: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def status(self) -> str:
        """draft（下書き）/ scheduled（予約）/ published（配信中）/ expired（終了）。"""
        if self.is_draft:
            return "draft"
        now = datetime.now(UTC)
        if self.publish_at and self.publish_at > now:
            return "scheduled"
        if self.expire_at and self.expire_at < now:
            return "expired"
        return "published"

    @property
    def target(self) -> dict:
        if not self.target_departments:
            return {"type": "all"}
        return {"type": "departments", "departments": list(self.target_departments)}

    def to_dict(self, read_count: int = 0, target_count: int = 0) -> dict:
        """API のレスポンス形式（docs/api-spec.md の Notice）に変換する。"""
        return {
            "id": str(self.id),
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "target": self.target,
            "channels": list(self.channels),
            "publishAt": _iso(self.publish_at),
            "expireAt": _iso(self.expire_at),
            "status": self.status,
            "createdBy": self.created_by_name,
            "createdAt": _iso(self.created_at),
            "readCount": read_count,
            "targetCount": target_count,
        }


class NoticeRead(db.Model):
    """利用者がお知らせを読んだ記録。"""

    __tablename__ = "notice_reads"
    __table_args__ = (UniqueConstraint("notice_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSetting(db.Model):
    """画面から変える設定（通知設定など）。1 つの設定を 1 行の JSON で保存する。"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
