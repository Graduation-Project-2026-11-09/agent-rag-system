import os
from datetime import timedelta


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app"
    )
    # しばらく使われずに切れた DB 接続を待ち続けて、API が固まらないようにする（stg で発生）
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # 使う前に接続が生きているか確認する
        "pool_recycle": 280,  # 5 分近く使っていない接続は作り直す
        "connect_args": {
            "connect_timeout": 5,
            # 応答のない接続を早めに切れたと判断する（既定では 2 時間以上かかる）
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            # Gunicorn の gthread ワーカーはリクエスト単位で打ち切らないため、DB 側で上限を設ける。
            # SQL の実行は 30 秒、ロック待ちは 5 秒、トランザクション中の放置は 60 秒まで
            "options": (
                "-c statement_timeout=30000"
                " -c lock_timeout=5000"
                " -c idle_in_transaction_session_timeout=60000"
            ),
        },
    }
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    # 使用するモデル（docs/architecture/ai.md「使用するモデル」）
    OPENAI_CHAT_MODEL_FAST = os.environ.get("OPENAI_CHAT_MODEL_FAST", "gpt-6-luna")
    OPENAI_CHAT_MODEL_ANSWER = os.environ.get("OPENAI_CHAT_MODEL_ANSWER", "gpt-6-luna")
    OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    # chunks.embedding の次元数（halfvec(3072)）。モデルを変えるときはマイグレーションも必要
    OPENAI_EMBEDDING_DIMENSIONS = int(os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "3072"))
    MAIL_HOST = os.environ.get("MAIL_HOST", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))

    # ログイン状態は HttpOnly の Cookie で管理する（非機能要件 No.18）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # HTTPS で配信している環境だけ true にする（HTTP のままだと Cookie が送られなくなる）
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
