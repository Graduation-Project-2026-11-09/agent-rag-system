import os
from datetime import timedelta


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app"
    )
    # RDS が停止・起動したあとに切れた接続を使わないようにする
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    MAIL_HOST = os.environ.get("MAIL_HOST", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))

    # ログイン状態は HttpOnly の Cookie で管理する（非機能要件 No.18）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # HTTPS で配信している環境だけ true にする（HTTP のままだと Cookie が送られなくなる）
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
