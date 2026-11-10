import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from conftest import login_as
from sqlalchemy import select

from app.extensions import db
from app.models import Conversation, Document, Message, User

# ---------- 問い合わせ ----------


@pytest.fixture
def people(make_user):
    return {
        "user": make_user("営業部", name="山田 花子"),
        "hr": make_user("人事部", "staff", handles_department="人事部", name="佐藤 美咲"),
        "it": make_user("情報システム部", "staff", handles_department="情報システム部"),
        "admin": make_user("情報システム部", "admin", handles_department="情報システム部"),
    }


def _assistant_message(user) -> Message:
    conversation = Conversation(user_id=user.id, title="時短勤務")
    message = Message(conversation=conversation, role="assistant", content="…", question="時短は？")
    db.session.add_all([conversation, message])
    db.session.commit()
    return message


def _send_inquiry(client, message_id=None, department="人事部"):
    return client.post(
        "/api/inquiries",
        json={
            "messageId": str(message_id) if message_id else None,
            "department": department,
            "subject": "時短勤務の延長",
            "body": "延長できますか",
            "context": {"question": "時短は？", "sources": ["育児・介護休業規程 第18条"]},
        },
    )


def test_inquiry_flow(client, people):
    message = _assistant_message(people["user"])
    login_as(client, people["user"])
    response = _send_inquiry(client, message.id)

    assert response.status_code == 201
    inquiry = response.get_json()
    assert inquiry["number"].startswith("INQ-")
    assert inquiry["status"] == "open"
    # 回答とつながり、利用履歴で「問い合わせ」として数えられる
    assert db.session.get(Message, message.id).result == "inquiry"
    assert _send_inquiry(client, message.id).status_code == 409

    login_as(client, people["hr"])
    url = f"/api/admin/inquiries/{inquiry['id']}"
    replied = client.post(f"{url}/replies", json={"body": "延長できます"}).get_json()
    assert replied["status"] == "in_progress"
    assert replied["assignee"] == "佐藤 美咲"
    assert client.patch(url, json={"status": "resolved"}).get_json()["status"] == "resolved"

    login_as(client, people["user"])
    mine = client.get("/api/inquiries/mine").get_json()
    assert mine[0]["replies"][0]["body"] == "延長できます"


def test_staff_sees_only_own_department_inquiries(client, people):
    login_as(client, people["user"])
    inquiry_id = _send_inquiry(client).get_json()["id"]

    login_as(client, people["it"])
    assert client.get("/api/admin/inquiries").get_json() == []
    assert client.get(f"/api/admin/inquiries/{inquiry_id}").status_code == 404

    login_as(client, people["admin"])
    assert len(client.get("/api/admin/inquiries").get_json()) == 1

    login_as(client, people["user"])
    assert client.get("/api/admin/inquiries").status_code == 403


def test_inquiry_search_by_number(client, people):
    login_as(client, people["user"])
    inquiry = _send_inquiry(client).get_json()
    login_as(client, people["hr"])

    found = client.get("/api/admin/inquiries", query_string={"q": inquiry["number"]}).get_json()
    assert [i["id"] for i in found] == [inquiry["id"]]


def test_cannot_attach_other_users_message(client, people, make_user):
    message = _assistant_message(make_user("開発部"))
    login_as(client, people["user"])
    assert _send_inquiry(client, message.id).status_code == 404


# ---------- お知らせ ----------


def _notice(**fields):
    return {
        "title": "年末調整のお知らせ",
        "body": "11月13日までに提出してください",
        "priority": "important",
        "target": {"type": "all"},
        "channels": ["in_app"],
        "publishAt": None,
        "expireAt": None,
        "isDraft": False,
        **fields,
    }


def test_notice_visibility_and_read(client, people):
    login_as(client, people["hr"])
    published = client.post("/api/admin/notices", json=_notice()).get_json()
    later = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    scheduled = client.post("/api/admin/notices", json=_notice(publishAt=later)).get_json()
    client.post("/api/admin/notices", json=_notice(isDraft=True))
    client.post(
        "/api/admin/notices",
        json=_notice(target={"type": "departments", "departments": ["開発部"]}),
    )
    assert published["status"] == "published"
    assert scheduled["status"] == "scheduled"

    login_as(client, people["user"])
    mine = client.get("/api/notices").get_json()
    # 予約・下書き・他部署向けは表示しない
    assert [n["id"] for n in mine] == [published["id"]]
    assert mine[0]["read"] is False
    assert client.post(f"/api/notices/{published['id']}/read").status_code == 204
    assert client.get("/api/notices").get_json()[0]["read"] is True

    login_as(client, people["hr"])
    listed = {n["id"]: n for n in client.get("/api/admin/notices").get_json()}
    assert listed[published["id"]]["readCount"] == 1
    assert listed[published["id"]]["targetCount"] == 4


def test_notice_validation(client, people):
    login_as(client, people["hr"])
    assert client.post("/api/admin/notices", json=_notice(title="")).status_code == 400
    assert client.post("/api/admin/notices", json=_notice(channels=[])).status_code == 400
    target = {"type": "departments", "departments": []}
    assert client.post("/api/admin/notices", json=_notice(target=target)).status_code == 400


def test_notification_settings(client, people):
    login_as(client, people["admin"])
    settings = client.get("/api/admin/notification-settings").get_json()
    settings["weeklyReport"]["enabled"] = False

    saved = client.put("/api/admin/notification-settings", json=settings).get_json()
    assert saved["weeklyReport"]["enabled"] is False
    assert client.get("/api/admin/notification-settings").get_json() == saved

    login_as(client, people["hr"])
    assert client.get("/api/admin/notification-settings").status_code == 403


# ---------- アカウント ----------

NEW_USER = {
    "employeeId": "E20001",
    "name": "新人 一郎",
    "email": "New@Example.co.jp",
    "department": "開発部",
    "role": "user",
    "handlesDepartment": None,
    "passwordMode": "password",
    "password": "long-enough-pass",
}


def test_create_and_update_user(client, people):
    login_as(client, people["admin"])
    created = client.post("/api/admin/users", json=NEW_USER).get_json()
    assert created["email"] == "new@example.co.jp"
    assert created["status"] == "active"
    assert client.post("/api/admin/users", json=NEW_USER).status_code == 409

    url = f"/api/admin/users/{created['id']}"
    updated = client.patch(url, json={"role": "staff", "status": "suspended"}).get_json()
    assert updated["role"] == "staff"
    assert updated["handlesDepartment"] == "開発部"
    assert updated["status"] == "suspended"
    assert client.delete(url).status_code == 204


def test_create_user_rejects_invite_and_short_password(client, people):
    login_as(client, people["admin"])
    invite = client.post("/api/admin/users", json={**NEW_USER, "passwordMode": "invite"})
    assert invite.status_code == 400
    assert "準備中" in invite.get_json()["message"]
    short = client.post("/api/admin/users", json={**NEW_USER, "password": "short"})
    assert short.status_code == 400


def test_bulk_create_reports_errors_per_row(client, people):
    login_as(client, people["admin"])
    rows = [
        {**NEW_USER, "email": "a@example.co.jp", "employeeId": "B1"},
        {**NEW_USER, "email": "a@example.co.jp", "employeeId": "B2"},  # 同じ CSV 内の重複
        {**NEW_USER, "email": "c@example.co.jp", "employeeId": "B3", "department": "存在しない部"},
    ]

    result = client.post("/api/admin/users/bulk", json={"users": rows}).get_json()

    assert result["created"] == 1
    assert [e["row"] for e in result["errors"]] == [2, 3]
    user = db.session.scalar(select(User).where(User.email == "a@example.co.jp"))
    assert user.status == "invited"


def test_admin_cannot_lock_themselves_out(client, people):
    login_as(client, people["admin"])
    url = f"/api/admin/users/{people['admin'].id}"
    assert client.patch(url, json={"status": "suspended"}).status_code == 400
    assert client.patch(url, json={"role": "user"}).status_code == 400
    assert client.delete(url).status_code == 400


def test_users_api_requires_admin(client, people):
    login_as(client, people["hr"])
    assert client.get("/api/admin/users").status_code == 403


# ---------- 資料 ----------

META = {
    "category": "人事手続き",
    "department": "人事部",
    "visibility": {"type": "all"},
    "tags": ["結婚"],
    "effectiveDate": "2026-04-01",
}


def _upload(client, meta=META, name="tetsuzuki.md", content="# 手続き\n結婚したら届け出る。\n"):
    return client.post(
        "/api/admin/documents",
        data={
            "file": (io.BytesIO(content.encode()), name),
            "meta": json.dumps(meta, ensure_ascii=False),
        },
        content_type="multipart/form-data",
    )


def test_document_upload_and_manage(client, people):
    login_as(client, people["hr"])
    response = _upload(client)
    assert response.status_code == 201
    document = response.get_json()
    assert document["status"] == "processing"
    assert document["uploadedBy"] == "佐藤 美咲"
    assert document["effectiveDate"] == "2026-04-01"

    url = f"/api/admin/documents/{document['id']}"
    detail = client.get(url).get_json()
    assert detail["versions"][0]["note"] == "初回登録"

    patched = client.patch(
        url,
        json={
            "title": "結婚の手続き",
            "visibility": {"type": "departments", "departments": ["人事部"]},
        },
    ).get_json()
    assert patched["title"] == "結婚の手続き"
    assert patched["visibility"] == {"type": "departments", "departments": ["人事部"]}

    assert client.post(f"{url}/reindex").get_json()["processingStage"] == "uploaded"
    assert client.delete(url).status_code == 204
    assert db.session.get(Document, int(document["id"])) is None


def test_staff_cannot_manage_other_department_documents(client, people):
    login_as(client, people["it"])
    assert _upload(client).status_code == 400  # 人事部の資料は登録できない

    login_as(client, people["hr"])
    document_id = _upload(client).get_json()["id"]
    login_as(client, people["it"])
    assert client.get("/api/admin/documents").get_json() == []
    assert client.delete(f"/api/admin/documents/{document_id}").status_code == 404


def test_upload_rejects_unsupported_file(client, people):
    login_as(client, people["hr"])
    response = _upload(client, name="budget.xlsx")
    assert response.status_code == 400
    assert "対応していない形式" in response.get_json()["message"]


def test_user_can_view_only_visible_documents(client, people):
    login_as(client, people["hr"])
    public_id = _upload(client).get_json()["id"]
    restricted_meta = {**META, "visibility": {"type": "departments", "departments": ["人事部"]}}
    restricted_id = _upload(client, meta=restricted_meta).get_json()["id"]

    login_as(client, people["user"])
    assert client.get(f"/api/documents/{public_id}").status_code == 200
    file = client.get(f"/api/documents/{public_id}/file")
    assert file.status_code == 200
    assert "結婚したら届け出る" in file.get_data(as_text=True)
    assert client.get(f"/api/documents/{restricted_id}").status_code == 404
    assert client.get(f"/api/documents/{restricted_id}/file").status_code == 404


# ---------- 利用履歴・マスタ ----------


def test_logs_and_summary(client, people):
    message = _assistant_message(people["user"])
    message.search_count, message.duration_ms, message.feedback = 2, 5000, "good"
    message.cost_usd = 0.05
    db.session.commit()

    login_as(client, people["admin"])
    logs = client.get("/api/admin/logs", query_string={"days": 30}).get_json()
    assert logs[0]["userName"] == "山田 花子"
    assert logs[0]["result"] == "resolved"
    assert client.get("/api/admin/logs", query_string={"result": "inquiry"}).get_json() == []

    summary = client.get("/api/admin/logs/summary").get_json()
    assert summary["total"] == 1
    assert summary["goodRate"] == 1
    assert summary["savedMinutes"] == 20
    assert summary["totalCostUsd"] == pytest.approx(0.05)


def test_masters(client, people):
    login_as(client, people["user"])
    assert "人事部" in client.get("/api/departments").get_json()
    assert "人事手続き" in client.get("/api/document-categories").get_json()
