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


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    _ensure_test_database()


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
