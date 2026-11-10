import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from app.config import Config
from app.extensions import db

# 開発用の DB を壊さないよう、テストは別のデータベース（<DB名>_test）を使う
_base_url = make_url(Config.SQLALCHEMY_DATABASE_URI)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _base_url.set(
    database=f"{_base_url.database}_test"
).render_as_string(hide_password=False)


def _ensure_test_database() -> None:
    test_db = make_url(TEST_DATABASE_URL).database
    engine = create_engine(_base_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_db})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    engine.dispose()

    # db/init の SQL は開発用の DB にしか実行されないため、テスト用の DB にも pgvector を入れる
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine.dispose()


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL
    # テストから OpenAI API や S3 を呼ばないようにする（呼ぶ処理はテストの中でモックにする）
    OPENAI_API_KEY = "test-key"
    DOCUMENTS_BUCKET = ""


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    _ensure_test_database()


@pytest.fixture
def app(tmp_path):
    app = create_app(TestConfig)
    app.config["DOCUMENTS_DIR"] = str(tmp_path / "documents")
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """利用者を作る。部署と権限を変えて、公開範囲や権限のテストに使う。"""
    from app.models import User

    count = 0

    def make(department: str = "営業部", role: str = "user", **fields) -> User:
        nonlocal count
        count += 1
        user = User(
            employee_id=fields.pop("employee_id", f"T{count:04d}"),
            name=fields.pop("name", f"テスト 利用者{count}"),
            email=fields.pop("email", f"user{count}@example.co.jp"),
            department=department,
            role=role,
            handles_department=fields.pop("handles_department", None),
            status=fields.pop("status", "active"),
        )
        user.set_password(fields.pop("password", "test-password-123"))
        db.session.add(user)
        db.session.commit()
        return user

    return make


def login_as(client, user) -> None:
    """パスワードの照合を省いてログイン状態にする（認証以外のテスト用）。"""
    with client.session_transaction() as session:
        session["user_id"] = user.id
