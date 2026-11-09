from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db

_hasher = PasswordHasher()

# 存在しないメールアドレスでも照合の時間をそろえ、登録の有無を推測されないようにするためのハッシュ
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

ROLES = ("user", "staff", "admin")
STATUSES = ("active", "invited", "suspended")


class User(db.Model):
    """システムの利用者（一般利用者・部署担当者・管理者）。

    Attributes:
        email: ログイン ID。小文字で保存する。
        role: 権限。user（一般利用者）/ staff（部署担当者）/ admin（管理者）。
        handles_department: 部署担当者が対応する問い合わせの部署。一般利用者は None。
        status: active（利用中）/ invited（招待中）/ suspended（利用停止）。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16), default="user")
    handles_department: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def set_password(self, password: str) -> None:
        """パスワードを argon2 でハッシュ化して保存する。"""
        self.password_hash = _hasher.hash(password)

    def check_password(self, password: str) -> bool:
        """パスワードが正しいか確認する。

        Args:
            password: 利用者が入力したパスワード。

        Returns:
            正しければ True。パスワード未設定（招待中など）の場合は False。
        """
        if not self.password_hash:
            verify_dummy_password(password)
            return False
        try:
            return _hasher.verify(self.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def to_dict(self) -> dict:
        """API のレスポンス形式（docs/api-spec.md の User）に変換する。"""
        return {
            "id": str(self.id),
            "employeeId": self.employee_id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "role": self.role,
            "handlesDepartment": self.handles_department,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
        }


def verify_dummy_password(password: str) -> None:
    """利用者が見つからない場合にも、照合と同じだけ時間をかける。"""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except VerifyMismatchError:
        pass
