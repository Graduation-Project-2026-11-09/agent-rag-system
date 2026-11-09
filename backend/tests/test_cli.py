from sqlalchemy import select

from app.extensions import db
from app.models import User

ARGS = [
    "create-user",
    "--email",
    "Member@Example.co.jp",
    "--name",
    "開発 メンバー",
    "--employee-id",
    "S0001",
    "--department",
    "情報システム部",
    "--role",
    "admin",
]


def test_create_user(app, monkeypatch):
    monkeypatch.setenv("SEED_USER_PASSWORD", "shared-password")
    result = app.test_cli_runner().invoke(args=ARGS)

    assert result.exit_code == 0, result.output
    user = db.session.scalar(select(User).where(User.email == "member@example.co.jp"))
    assert user.role == "admin"
    assert user.check_password("shared-password")


def test_create_user_skips_existing_email(app, monkeypatch):
    monkeypatch.setenv("SEED_USER_PASSWORD", "shared-password")
    runner = app.test_cli_runner()
    runner.invoke(args=ARGS)
    result = runner.invoke(args=ARGS)

    assert result.exit_code == 0
    assert "登録済み" in result.output
    assert len(db.session.scalars(select(User)).all()) == 1


def test_create_user_requires_password(app, monkeypatch):
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)
    result = app.test_cli_runner().invoke(args=ARGS)
    assert result.exit_code != 0
