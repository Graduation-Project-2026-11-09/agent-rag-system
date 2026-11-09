from sqlalchemy import text

from app.extensions import db


def test_db_session_has_time_limits(app):
    """固まった処理で API 全体が止まらないよう、接続ごとに時間の上限が設定されている。"""
    assert db.session.scalar(text("SHOW statement_timeout")) == "30s"
    assert db.session.scalar(text("SHOW lock_timeout")) == "5s"
    assert db.session.scalar(text("SHOW idle_in_transaction_session_timeout")) == "1min"
