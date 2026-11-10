from datetime import UTC, datetime

import pytest
from fake_ai import ScriptedLLM, fake_embed_texts, topic_vector

from app.ai import agent, retrieval
from app.ai.agent import (
    NOT_FOUND_CONTENT,
    Analysis,
    Answer,
    Evaluation,
    Expansion,
    InquiryDraft,
    NextStep,
    build_sources,
)
from app.ai.llm import Usage
from app.ai.retrieval import SearchHit, Viewer, search_chunks
from app.extensions import db
from app.models import Document, DocumentChunk, DocumentVersion


def _add_document(title, department, chunks, visible_departments=None):
    document = Document(
        title=title,
        department=department,
        visibility_type="departments" if visible_departments else "all",
        visible_departments=visible_departments or [],
        tags=[],
        status="indexed",
        current_version=1,
    )
    version = DocumentVersion(
        document=document,
        version=1,
        file_name=f"{title}.pdf",
        file_type="pdf",
        size=1,
        storage_key=f"documents/{title}",
    )
    db.session.add_all([document, version])
    db.session.flush()
    for index, (section, content) in enumerate(chunks):
        db.session.add(
            DocumentChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_index=index,
                section=section,
                page=index + 1,
                content=content,
                embedding=topic_vector(content),
            )
        )
    db.session.commit()
    return document


@pytest.fixture
def documents(app, monkeypatch):
    monkeypatch.setattr(retrieval, "embed_texts", fake_embed_texts)
    _add_document(
        "就業規則", "人事部", [("第32条（特別休暇）", "結婚したときは5日の休暇を与える。")]
    )
    _add_document(
        "慶弔見舞金規程", "総務部", [("第5条（結婚祝金）", "結婚祝金として30,000円を支給する。")]
    )
    _add_document("経費精算マニュアル", "経理部", [("2.1 締め日", "経費の締め日は毎月末日。")])
    _add_document(
        "人事評価マニュアル",
        "人事部",
        [("3.2 分布の目安", "評価の分布は S 5%、A 20%。")],
        visible_departments=["人事部"],
    )


def _viewer(department="営業部", role="user"):
    return Viewer(id=1, name="山田 花子", department=department, role=role)


# ---------- 検索（公開範囲の絞り込み） ----------


def test_search_returns_similar_chunks(documents):
    hits = search_chunks(["結婚 手続き"], _viewer(), Usage())

    assert {hit.title for hit in hits} == {"就業規則", "慶弔見舞金規程"}
    assert all(hit.score > 0.7 for hit in hits)


def test_search_excludes_documents_of_other_departments(documents):
    hits = search_chunks(["人事評価 分布"], _viewer("営業部"), Usage())
    assert "人事評価マニュアル" not in {hit.title for hit in hits}


def test_search_includes_documents_of_own_department(documents):
    hits = search_chunks(["人事評価 分布"], _viewer("人事部"), Usage())
    assert hits[0].title == "人事評価マニュアル"


def test_admin_can_search_all_documents(documents):
    hits = search_chunks(["人事評価 分布"], _viewer("情報システム部", "admin"), Usage())
    assert hits[0].title == "人事評価マニュアル"


def test_search_drops_unrelated_chunks(documents):
    assert search_chunks(["社員旅行"], _viewer(), Usage()) == []


# ---------- 検索Agent ----------

ANALYSIS = Analysis(
    intent="結婚の手続きを知りたい",
    aspects=["結婚休暇", "結婚祝金"],
    department="人事部",
    is_work_question=True,
)
ANSWER = Answer(
    content="結婚休暇は **5日** です [1]。祝金は **30,000円** です [2]。",
    cited=[1, 2],
    status="answered",
    next_steps=[
        NextStep(title="特別休暇申請", description="勤怠システム", department="", deadline="")
    ],
    unresolved=[],
)
DRAFT = InquiryDraft(subject="件名", body="本文", reason="資料に記載がないため")


def _run(generator):
    steps = []
    while True:
        try:
            steps.append(next(generator))
        except StopIteration as finished:
            return steps, finished.value


@pytest.fixture
def llm(monkeypatch):
    def install(**outputs):
        scripted = ScriptedLLM(outputs)
        monkeypatch.setattr(agent, "call_structured", scripted)
        return scripted

    return install


def test_agentic_answers_when_information_is_sufficient(documents, llm):
    scripted = llm(
        analyze=[ANALYSIS],
        expand=[Expansion(queries=["結婚 休暇", "結婚 祝金"], strategy="言い換えて検索")],
        evaluate=[Evaluation(sufficient=True, covered=["結婚休暇"], missing=[], reason="十分")],
        answer=[ANSWER],
    )

    steps, result = _run(agent.run_agentic("結婚しました", _viewer(), []))

    assert [s["type"] for s in steps] == ["analyze", "plan", "search", "evaluate", "generate"]
    assert result.search_count == 1
    assert result.answer_status == "answered"
    assert result.inquiry_suggestion is None
    assert [s["index"] for s in result.sources] == [1, 2]
    assert result.next_steps[0]["department"] is None  # 空文字は「なし」にする
    assert result.usage.input_tokens > 0
    assert scripted.called("inquiry") == 0


def test_agentic_searches_again_only_once(documents, llm):
    insufficient = Evaluation(sufficient=False, covered=[], missing=["祝金の金額"], reason="不足")
    scripted = llm(
        analyze=[ANALYSIS],
        expand=[
            Expansion(queries=["結婚 休暇"], strategy="検索"),
            Expansion(queries=["結婚 祝金 金額"], strategy="再検索"),
        ],
        evaluate=[insufficient],
        answer=[ANSWER],
    )

    steps, result = _run(agent.run_agentic("結婚しました", _viewer(), []))

    # 2 回目の評価でも不足のままだが、再検索は 1 回で打ち切って回答する
    assert result.search_count == 2
    assert scripted.called("expand") == 2
    assert [s["title"] for s in steps if s["type"] == "search"] == [
        "社内資料を検索（1回目）",
        "追加検索（2回目）",
    ]
    # 追加検索の内容は、前回の不足を伝えて作らせる
    assert "祝金の金額" in [i for n, i in scripted.calls if n == "expand"][1]


def test_agentic_does_not_answer_without_sources(documents, llm):
    scripted = llm(
        analyze=[ANALYSIS.model_copy(update={"department": "総務部"})],
        expand=[Expansion(queries=["社員旅行 日程"], strategy="検索")],
        evaluate=[Evaluation(sufficient=False, covered=[], missing=["日程"], reason="なし")],
        inquiry=[DRAFT],
    )

    _, result = _run(agent.run_agentic("社員旅行はいつ？", _viewer(), []))

    # 根拠がないときは AI に回答を作らせず、問い合わせを提案する（ルール 6）
    assert scripted.called("answer") == 0
    assert result.content == NOT_FOUND_CONTENT
    assert result.answer_status == "not_found"
    assert result.sources == []
    assert result.inquiry_suggestion["department"] == "総務部"


def test_partial_answer_suggests_inquiry(documents, llm):
    partial = ANSWER.model_copy(update={"status": "partial", "unresolved": ["海外の日当"]})
    scripted = llm(
        analyze=[ANALYSIS.model_copy(update={"department": "経理部"})],
        expand=[Expansion(queries=["経費 締め日"], strategy="検索")],
        evaluate=[Evaluation(sufficient=True, covered=[], missing=[], reason="")],
        answer=[partial.model_copy(update={"content": "締め日は月末です [1]。", "cited": [1]})],
        inquiry=[DRAFT],
    )

    _, result = _run(agent.run_agentic("海外出張の日当は？", _viewer(), []))

    assert result.inquiry_suggestion == {
        "department": "経理部",
        "reason": DRAFT.reason,
        "subject": DRAFT.subject,
        "body": DRAFT.body,
    }
    assert "海外の日当" in [i for n, i in scripted.calls if n == "inquiry"][0]


def test_non_work_question_is_not_searched(documents, llm):
    scripted = llm(analyze=[ANALYSIS.model_copy(update={"is_work_question": False})])

    steps, result = _run(agent.run_agentic("こんにちは", _viewer(), []))

    assert [s["type"] for s in steps] == ["analyze", "generate"]
    assert result.search_count == 0
    assert scripted.called("expand") == 0


def test_basic_rag_searches_once_with_question(documents, llm):
    scripted = llm(answer=[ANSWER])

    steps, result = _run(agent.run_basic("結婚したときの休暇と祝金", _viewer(), []))

    assert [s["type"] for s in steps] == ["search", "generate"]
    assert result.mode == "basic"
    assert scripted.called("analyze") == 0


def test_restricted_document_is_never_given_to_ai(documents, llm):
    scripted = llm(
        analyze=[ANALYSIS],
        expand=[Expansion(queries=["人事評価 分布"], strategy="検索")],
        evaluate=[Evaluation(sufficient=False, covered=[], missing=[], reason="")],
        inquiry=[DRAFT],
    )

    _run(agent.run_agentic("評価の分布は？", _viewer("営業部"), []))

    assert all("S 5%" not in user_input for _, user_input in scripted.calls)


# ---------- 根拠資料の番号 ----------


def _hit(number):
    return SearchHit(
        chunk_id=number,
        document_id=number,
        title=f"資料{number}",
        file_type="pdf",
        department="人事部",
        updated_at=datetime(2026, 4, 1, tzinfo=UTC),
        section=f"第{number}条",
        page=number,
        content=f"本文{number}",
        score=0.9,
    )


def test_build_sources_renumbers_and_drops_unknown_citations():
    answer = ANSWER.model_copy(
        update={"content": "A です [3]。B です [1]。C です [9]。", "cited": [3, 1]}
    )

    content, sources = build_sources(answer, [_hit(1), _hit(2), _hit(3)])

    assert content == "A です [1]。B です [2]。C です 。"
    assert [(s["index"], s["title"]) for s in sources] == [(1, "資料3"), (2, "資料1")]
    assert sources[0]["excerpt"] == "本文3"
