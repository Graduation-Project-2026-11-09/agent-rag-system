"""ログイン状態の管理。ログイン中の利用者 ID は Flask のセッション Cookie（HttpOnly）に保存する。"""

from functools import wraps

from flask import jsonify, session

from .extensions import db
from .models import User

SESSION_USER_KEY = "user_id"


def login_user(user: User) -> None:
    """利用者をログイン状態にする。

    セッション固定攻撃を防ぐため、既存のセッションを破棄してから保存する。
    """
    session.clear()
    session[SESSION_USER_KEY] = user.id
    session.permanent = True


def logout_user() -> None:
    session.clear()


def current_user() -> User | None:
    """ログイン中の利用者を返す。

    ログイン後に利用停止・削除された場合も、その時点でログアウト扱いにする。

    Returns:
        ログイン中で、利用中（active）の利用者。それ以外は None。
    """
    user_id = session.get(SESSION_USER_KEY)
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    if user is None or user.status != "active":
        session.clear()
        return None
    return user


def login_required(view):
    """ログインしていなければ 401 を返すデコレータ。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify(message="ログインしてください"), 401
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles: str):
    """ログインしていなければ 401、権限が roles に含まれなければ 403 を返すデコレータ。

    Args:
        roles: 利用できる権限（user / staff / admin）。
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify(message="ログインしてください"), 401
            if user.role not in roles:
                return jsonify(message="この操作を行う権限がありません"), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator


def handles(user: User, department: str) -> bool:
    """利用者が、その部署あての問い合わせや資料を扱えるか。管理者はすべて扱える。"""
    return user.role == "admin" or (user.role == "staff" and user.handles_department == department)
