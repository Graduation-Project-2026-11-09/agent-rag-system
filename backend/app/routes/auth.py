from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import current_user, login_required, login_user, logout_user
from ..extensions import db
from ..models import User
from ..models.user import verify_dummy_password

bp = Blueprint("auth", __name__)

# 利用者が存在するか・パスワードが違うかを区別できないよう、同じ文言にする
INVALID_CREDENTIALS = "メールアドレスまたはパスワードが正しくありません"


@bp.post("/auth/login")
def login():
    """メールアドレスとパスワードでログインする。"""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if not email or not password:
        return jsonify(message="メールアドレスとパスワードを入力してください"), 400

    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        verify_dummy_password(password)
        return jsonify(message=INVALID_CREDENTIALS), 401
    if not user.check_password(password):
        return jsonify(message=INVALID_CREDENTIALS), 401
    if user.status == "suspended":
        return jsonify(message="このアカウントは利用停止中です"), 403
    if user.status == "invited":
        return jsonify(message="招待メールからパスワードを設定してください"), 403

    user.last_login_at = datetime.now(UTC)
    db.session.commit()
    login_user(user)
    return jsonify(user.to_dict())


@bp.post("/auth/logout")
def logout():
    logout_user()
    return "", 204


@bp.get("/auth/me")
@login_required
def me():
    """ログイン中の利用者を返す。画面の再読み込み時にログイン状態を復元するために使う。"""
    return jsonify(current_user().to_dict())
