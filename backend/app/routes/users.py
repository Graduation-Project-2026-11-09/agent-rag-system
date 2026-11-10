"""アカウント管理（管理者）の API。"""

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from ..auth import current_user, roles_required
from ..extensions import db
from ..masters import DEPARTMENTS
from ..models import User
from ..models.user import ROLES, STATUSES
from .helpers import BadRequest, error, json_body, required_text

bp = Blueprint("users", __name__)

MIN_PASSWORD_LENGTH = 12  # 情報セキュリティポリシー第12条と同じ
# 招待メール・パスワード再設定はメールを送る仕組みができるまで作らない（ai.md 参照）
INVITE_NOT_READY = "招待メールは準備中です。「パスワードを設定」を選んでください"


class Conflict(Exception):
    """メールアドレスや社員番号が登録済み。"""


@bp.errorhandler(BadRequest)
def _bad_request(e: BadRequest):
    return error(str(e), 400)


@bp.errorhandler(Conflict)
def _conflict(e: Conflict):
    return error(str(e), 409)


@bp.get("/admin/users")
@roles_required("admin")
def list_users():
    query = select(User).order_by(User.id)
    if keyword := request.args.get("q", "").strip():
        pattern = f"%{keyword}%"
        query = query.where(
            or_(
                User.name.ilike(pattern), User.email.ilike(pattern), User.employee_id.ilike(pattern)
            )
        )
    for key, column in [
        ("department", User.department),
        ("role", User.role),
        ("status", User.status),
    ]:
        if value := request.args.get(key):
            query = query.where(column == value)
    return jsonify([u.to_dict() for u in db.session.scalars(query)])


def _validate_profile(data: dict) -> dict:
    """氏名・メールアドレス・部署・権限を確かめ、User のカラム名の辞書にする。"""
    email = required_text(data, "email", "メールアドレス", 255).lower()
    if "@" not in email:
        raise BadRequest("メールアドレスの形式が正しくありません")
    department = str(data.get("department") or "")
    if department not in DEPARTMENTS:
        raise BadRequest("所属部署を選択してください")
    role = data.get("role") or "user"
    if role not in ROLES:
        raise BadRequest("権限の値が正しくありません")
    handles = None
    if role != "user":
        # 部署担当者・管理者は対応する部署を持つ。指定がなければ所属部署にする（モックと同じ）
        handles = str(data.get("handlesDepartment") or "") or department
        if handles not in DEPARTMENTS:
            raise BadRequest("担当部署の値が正しくありません")
    return {
        "employee_id": required_text(data, "employeeId", "社員番号", 32),
        "name": required_text(data, "name", "氏名", 100),
        "email": email,
        "department": department,
        "role": role,
        "handles_department": handles,
    }


def _ensure_unique(email: str, employee_id: str, exclude_id: int | None = None) -> None:
    """メールアドレスと社員番号が他のアカウントと重ならないか確かめる。

    Raises:
        Conflict: すでに登録されている場合。
    """
    checks = [
        (User.email, email, email),
        (User.employee_id, employee_id, f"社員番号 {employee_id}"),
    ]
    for column, value, label in checks:
        query = select(User.id).where(column == value)
        if exclude_id is not None:
            query = query.where(User.id != exclude_id)
        if db.session.scalar(query) is not None:
            raise Conflict(f"{label} はすでに登録されています")


def _set_password(user: User, password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise BadRequest(f"パスワードは {MIN_PASSWORD_LENGTH} 文字以上にしてください")
    user.set_password(password)


@bp.post("/admin/users")
@roles_required("admin")
def create_user():
    """アカウントを作る。パスワードは管理者が設定する（招待メールは準備中）。"""
    data = json_body()
    if data.get("passwordMode", "password") == "invite":
        raise BadRequest(INVITE_NOT_READY)
    profile = _validate_profile(data)
    _ensure_unique(profile["email"], profile["employee_id"])
    user = User(**profile, status="active")
    _set_password(user, str(data.get("password") or ""))
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.post("/admin/users/bulk")
@roles_required("admin")
def bulk_create():
    """CSV の内容でアカウントをまとめて作る。

    招待メールが準備中のため、作ったアカウントは「招待中」（パスワード未設定・ログイン不可）になる。
    行ごとに確認し、問題のある行は飛ばしてエラーとして返す。
    """
    rows = json_body().get("users")
    if not isinstance(rows, list):
        raise BadRequest("登録する行がありません")
    created, errors = 0, []
    for number, row in enumerate(rows, start=1):
        try:
            if not isinstance(row, dict):
                raise BadRequest("行の形式が正しくありません")
            profile = _validate_profile(row)
            _ensure_unique(profile["email"], profile["employee_id"])
        except (BadRequest, Conflict) as e:
            errors.append({"row": number, "message": str(e)})
            continue
        db.session.add(User(**profile, status="invited"))
        db.session.flush()  # 同じ CSV の中の重複も検出できるようにする
        created += 1
    db.session.commit()
    return jsonify(created=created, errors=errors)


@bp.patch("/admin/users/<int:user_id>")
@roles_required("admin")
def update_user(user_id: int):
    """アカウントの内容を変える。status を変えると利用停止・再開になる。"""
    user = db.session.get(User, user_id)
    if user is None:
        return error("アカウントが見つかりません", 404)
    data = json_body()
    me = current_user()
    changes_own_access = data.get("status") == "suspended" or data.get("role", "admin") != "admin"
    if user.id == me.id and changes_own_access:
        # 管理者が自分を停止・降格すると、誰も管理できなくなるおそれがあるため
        raise BadRequest("自分自身の利用停止や権限の変更はできません")

    profile = _validate_profile({**_profile_of(user), **data})
    _ensure_unique(profile["email"], profile["employee_id"], exclude_id=user.id)
    for key, value in profile.items():
        setattr(user, key, value)
    if "status" in data:
        if data["status"] not in STATUSES:
            raise BadRequest("利用状態の値が正しくありません")
        user.status = data["status"]
    db.session.commit()
    return jsonify(user.to_dict())


def _profile_of(user: User) -> dict:
    return {
        "employeeId": user.employee_id,
        "name": user.name,
        "email": user.email,
        "department": user.department,
        "role": user.role,
        "handlesDepartment": user.handles_department,
    }


@bp.delete("/admin/users/<int:user_id>")
@roles_required("admin")
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error("アカウントが見つかりません", 404)
    if user.id == current_user().id:
        raise BadRequest("自分自身のアカウントは削除できません")
    db.session.delete(user)
    db.session.commit()
    return "", 204
