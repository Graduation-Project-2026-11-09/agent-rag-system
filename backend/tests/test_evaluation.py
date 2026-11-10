import json
from types import SimpleNamespace

import pytest
from fake_ai import ScriptedLLM, fake_embed_texts
from test_agent import ANALYSIS, ANSWER, DRAFT, _add_document

from app import evaluation
from app.ai import agent, retrieval
from app.ai.agent import Evaluation, Expansion

# 出力の形（JSON Schema の名前）ごとに、偽の Batch API が返す出力
OUTPUTS = {
    "Analysis": ANALYSIS,
    "Expansion": Expansion(queries=["結婚 休暇"], strategy="検索"),
    "Evaluation": Evaluation(sufficient=True, covered=[], missing=[], reason="十分"),
    "Answer": ANSWER,
    "InquiryDraft": DRAFT,
}


class FakeBatchClient:
    """送られたリクエストに、すぐ「完了」の結果を返す偽の Batch API。"""

    def __init__(self):
        self.uploaded: dict[str, list[dict]] = {}
        self.batch_inputs: dict[str, str] = {}
        # OpenAI のクライアントと同じ client.files / client.batches の形にする
        self.files = SimpleNamespace(create=self._create_file, content=self._content)
        self.batches = SimpleNamespace(create=self._create_batch, retrieve=self._retrieve)

    def _create_file(self, file, purpose):
        file_id = f"file-{len(self.uploaded)}"
        self.uploaded[file_id] = [json.loads(line) for line in file[1].getvalue().splitlines()]
        return SimpleNamespace(id=file_id)

    def _create_batch(self, input_file_id, endpoint, completion_window):
        batch_id = f"batch-{len(self.batch_inputs)}"
        self.batch_inputs[batch_id] = input_file_id
        return SimpleNamespace(id=batch_id)

    def _retrieve(self, batch_id):
        return SimpleNamespace(
            status="completed",
            output_file_id=f"out-{self.batch_inputs[batch_id]}",
            error_file_id=None,
            request_counts=None,
        )

    def _content(self, file_id):
        lines = []
        for request in self.uploaded[file_id.removeprefix("out-")]:
            name = request["body"]["text"]["format"]["name"]
            body = {
                "model": request["body"]["model"],
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": OUTPUTS[name].model_dump_json()}
                        ],
                    }
                ],
            }
            lines.append(
                json.dumps(
                    {
                        "custom_id": request["custom_id"],
                        "response": {"status_code": 200, "body": body},
                    }
                )
            )
        return SimpleNamespace(text="\n".join(lines))


@pytest.fixture
def setup(app, tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(retrieval, "embed_texts", fake_embed_texts)
    _add_document(
        "就業規則", "人事部", [("第32条（特別休暇）", "結婚したときは5日の休暇を与える。")]
    )
    client = FakeBatchClient()
    monkeypatch.setattr(evaluation, "get_openai_client", lambda: client)
    return client


def test_batch_run_goes_through_all_stages(setup):
    run = evaluation.create_run(["basic", "agentic"], ["q01", "q46"])

    messages = [evaluation.advance(run)]
    for _ in range(10):
        run = evaluation.Run.load(run.run_id)
        messages.append(evaluation.advance(run))
        if messages[-1].startswith("評価が終わりました"):
            break

    run = evaluation.Run.load(run.run_id)
    assert run.is_finished
    assert all(item.stage == "done" for item in run.items), [i.data.get("error") for i in run.items]
    agentic = next(i for i in run.items if i.key == "q01:agentic")
    assert agentic.data["sources"][0]["title"] == "就業規則"
    # Batch API は半額で計算する
    assert agentic.usage["cost_usd"] > 0
    # 社員旅行（資料にない）は回答を作らせず、問い合わせを提案する
    travel = next(i for i in run.items if i.key == "q46:basic")
    assert travel.data["answer_status"] == "not_found"
    assert travel.data["inquiry_suggestion"]["department"]

    report = (run.path / "report.md").read_text(encoding="utf-8")
    assert "| agentic | 2 |" in report
    assert "q01:agentic" in report


def test_sync_run_measures_duration(setup, monkeypatch):
    monkeypatch.setattr(
        agent,
        "call_structured",
        ScriptedLLM(
            {
                "analyze": [ANALYSIS],
                "expand": [OUTPUTS["Expansion"]],
                "evaluate": [OUTPUTS["Evaluation"]],
                "answer": [ANSWER],
                "inquiry": [DRAFT],
            }
        ),
    )
    run = evaluation.create_run(["agentic"], ["q01"])

    evaluation.run_sync(run)

    item = evaluation.Run.load(run.run_id).items[0]
    assert item.stage == "done"
    assert "duration_ms" in item.data
    assert "就業規則|第32条（特別休暇）" in item.data["retrieved"]


def test_score_item():
    item = evaluation.Item(
        key="q11:agentic",
        question_id="q11",
        mode="agentic",
        stage="done",
        data={
            "question": {
                "expectedSources": [{"title": "経費精算マニュアル", "section": "4.3 出張旅費"}],
                "expectInquiry": {"department": "経理部"},
            },
            "sources": [{"title": "経費精算マニュアル", "section": "4.3 出張旅費"}],
            "retrieved": ["経費精算マニュアル|4.3 出張旅費"],
            "inquiry_suggestion": {"department": "経理部"},
        },
        usage={},
    )

    assert evaluation.score_item(item) == {
        "retrievalRecall": 1.0,
        "citationRecall": 1.0,
        "inquiryCorrect": True,
        "error": None,
    }
