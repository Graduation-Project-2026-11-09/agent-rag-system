import pytest

from app.extensions import db
from app.models import User

PASSWORD = "correct-horse-battery"


@pytest.fixture
def user(app):
    u = User(
        employee_id="E10234",
        name="山田 花子",
        email="yamada@example.co.jp",
        department="営業部",
        role="user",
        status="active",
    )
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    return u


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success_returns_user_and_sets_httponly_cookie(client, user):
    res = login(client, "yamada@example.co.jp", PASSWORD)

    assert res.status_code == 200
    body = res.get_json()
    assert body["email"] == "yamada@example.co.jp"
    assert body["employeeId"] == "E10234"
    assert body["role"] == "user"
    assert body["lastLoginAt"] is not None
    assert "password" not in str(body).lower()
    assert "HttpOnly" in res.headers["Set-Cookie"]


def test_login_email_is_case_insensitive(client, user):
    assert login(client, "  Yamada@Example.co.jp ", PASSWORD).status_code == 200


def test_login_wrong_password(client, user):
    res = login(client, "yamada@example.co.jp", "wrong")
    assert res.status_code == 401
    assert res.get_json()["message"] == "メールアドレスまたはパスワードが正しくありません"


def test_login_unknown_email_has_same_message(client, user):
    res = login(client, "nobody@example.co.jp", PASSWORD)
    assert res.status_code == 401
    assert res.get_json()["message"] == "メールアドレスまたはパスワードが正しくありません"


def test_login_requires_email_and_password(client):
    assert login(client, "", "").status_code == 400


def test_suspended_user_cannot_login(client, user):
    user.status = "suspended"
    db.session.commit()
    res = login(client, "yamada@example.co.jp", PASSWORD)
    assert res.status_code == 403


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_logged_in_user(client, user):
    login(client, "yamada@example.co.jp", PASSWORD)
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.get_json()["name"] == "山田 花子"


def test_logout_clears_session(client, user):
    login(client, "yamada@example.co.jp", PASSWORD)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_user_suspended_after_login_is_logged_out(client, user):
    login(client, "yamada@example.co.jp", PASSWORD)
    user.status = "suspended"
    db.session.commit()
    assert client.get("/api/auth/me").status_code == 401
