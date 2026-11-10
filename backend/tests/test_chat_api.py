import json

import pytest
from conftest import login_as
from fake_ai import ScriptedLLM, fake_embed_texts
from test_agent import _add_document

from app.ai import agent, retrieval
from app.ai.agent import Analysis, Answer, Evaluation, Expansion
from app.ai.llm import LLMError
from app.extensions import db
from app.models import Message


@pytest.fixture
def user(make_user):
    return make_user("営業部")


@pytest.fixture
def client_as_user(client, user):
    login_as(client, user)
    return client


@pytest.fixture
def scripted_agent(app, monkeypatch):
    monkeypatch.setattr(retrieval, "embed_texts", fake_embed_texts)
    _add_document("経費精算マニュアル", "経理部", [("2.1 締め日", "経費の締め日は毎月末日。")])
    scripted = ScriptedLLM(
        {
            "analyze": [
                Analysis(
                    intent="締め日", aspects=["締め日"], department="経理部", is_work_question=True
                )
            ],
            "expand": [Expansion(queries=["経費 締め日"], strategy="検索")],
            "evaluate": [Evaluation(sufficient=True, covered=[], missing=[], reason="十分")],
            "answer": [
                Answer(
                    content="締め日は **毎月末日** です [1]。",
                    cited=[1],
                    status="answered",
                    next_steps=[],
                    unresolved=[],
                )
            ],
        }
    )
    monkeypatch.setattr(agent, "call_structured", scripted)
    return scripted


def _events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.get_data(as_text=True).strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _create(client, title="経費精算の締め日はいつ？"):
    return client.post("/api/conversations", json={"title": title}).get_json()


def test_conversation_crud(client_as_user):
    created = _create(client_as_user, "とても長いタイトルの会話はモックと同じ24文字で切られます")
    assert len(created["title"]) == 24

    listed = client_as_user.get("/api/conversations").get_json()
    assert [c["id"] for c in listed] == [created["id"]]

    detail = client_as_user.get(f"/api/conversations/{created['id']}").get_json()
    assert detail["messages"] == []

    assert client_as_user.delete(f"/api/conversations/{created['id']}").status_code == 204
    assert client_as_user.get("/api/conversations").get_json() == []


def test_cannot_read_other_users_conversation(client, make_user):
    owner, other = make_user("営業部"), make_user("開発部")
    login_as(client, owner)
    conversation = _create(client)

    login_as(client, other)
    assert client.get(f"/api/conversations/{conversation['id']}").status_code == 404
    assert client.delete(f"/api/conversations/{conversation['id']}").status_code == 404


def test_requires_login(client):
    assert client.get("/api/conversations").status_code == 401


def test_send_message_streams_steps_and_answer(client_as_user, scripted_agent):
    conversation = _create(client_as_user)

    response = client_as_user.post(
        f"/api/conversations/{conversation['id']}/messages", json={"content": "締め日は？"}
    )

    assert response.mimetype == "text/event-stream"
    events = _events(response)
    assert [name for name, _ in events] == ["step"] * 5 + ["answer"]
    answer = events[-1][1]
    assert answer["role"] == "assistant"
    assert answer["sources"][0]["title"] == "経費精算マニュアル"
    assert answer["agent"]["searchCount"] == 1

    detail = client_as_user.get(f"/api/conversations/{conversation['id']}").get_json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    saved = db.session.get(Message, int(answer["id"]))
    assert saved.question == "締め日は？"
    assert saved.input_tokens > 0
    assert saved.result == "resolved"


def test_send_message_reports_ai_error(client_as_user, scripted_agent, monkeypatch):
    def fail(stage, user_input, usage):
        raise LLMError("analyze: AI の呼び出しに失敗しました")

    monkeypatch.setattr(agent, "call_structured", fail)
    conversation = _create(client_as_user)

    response = client_as_user.post(
        f"/api/conversations/{conversation['id']}/messages", json={"content": "締め日は？"}
    )

    assert _events(response) == [
        ("error", {"message": "回答の生成に失敗しました。時間をおいてもう一度お試しください"})
    ]


def test_send_message_validates_content(client_as_user):
    conversation = _create(client_as_user)
    url = f"/api/conversations/{conversation['id']}/messages"
    assert client_as_user.post(url, json={"content": " "}).status_code == 400
    assert client_as_user.post(url, json={"content": "あ" * 2001}).status_code == 400


def test_feedback(client_as_user, scripted_agent):
    conversation = _create(client_as_user)
    response = client_as_user.post(
        f"/api/conversations/{conversation['id']}/messages", json={"content": "締め日は？"}
    )
    message_id = _events(response)[-1][1]["id"]
    url = f"/api/messages/{message_id}/feedback"

    assert client_as_user.post(url, json={"feedback": "good"}).status_code == 204
    assert db.session.get(Message, int(message_id)).feedback == "good"
    assert client_as_user.post(url, json={"feedback": None}).status_code == 204
    assert client_as_user.post(url, json={"feedback": "great"}).status_code == 400
