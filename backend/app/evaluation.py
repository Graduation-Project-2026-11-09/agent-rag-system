"""評価用の質問セット（evaluation/questions.json）で、通常の RAG と検索Agent を比べる。

OpenAI の Batch API を使うと料金は半額になるが、1 回の結果を受け取るまで最大 24 時間かかる。
検索Agent は ①〜⑤ を順に呼ぶため、段階ごとに全問をまとめて 1 つの Batch にし、
結果が届いたら次の段階を送る。途中の状態は runs/<実行 ID>/state.json に保存し、
`flask evaluate advance` を実行するたびに進める（手元の PC を止めても続きから再開できる）。

Batch API では回答時間を測れないため、時間を測るときは `--sync` で 1 問ずつ実行する。
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from .ai import agent
from .ai.agent import (
    ANALYZE,
    ANSWER,
    EVALUATE,
    EXPAND,
    MAX_ASPECTS,
    MAX_QUERIES,
    MAX_RESEARCH_COUNT,
    NOT_FOUND_CONTENT,
    NOT_WORK_CONTENT,
    Analysis,
    Evaluation,
)
from .ai.client import get_openai_client
from .ai.llm import LLMError, Stage, Usage, build_request, parse_output
from .ai.retrieval import SearchHit, Viewer, search_chunks

log = logging.getLogger(__name__)

EVALUATION_DIR = Path(__file__).resolve().parent.parent / "evaluation"
QUESTIONS_PATH = EVALUATION_DIR / "questions.json"
RUNS_DIR = EVALUATION_DIR / "runs"
MODES = ("basic", "agentic")
BATCH_RATE = 0.5  # Batch API の料金は通常の半額


class EvaluationError(Exception):
    """評価を進められない。メッセージはコマンドの出力にそのまま表示する。"""


def load_questions(ids: list[str] | None = None) -> list[dict]:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    if ids:
        questions = [q for q in questions if q["id"] in ids]
    return questions


def _viewer(question: dict) -> Viewer:
    user = question["user"]
    return Viewer(id=0, name="評価 太郎", department=user["department"], role=user["role"])


def _hit_to_dict(hit: SearchHit) -> dict:
    data = asdict(hit)
    data["updated_at"] = hit.updated_at.isoformat()
    return data


def _hit_from_dict(data: dict) -> SearchHit:
    return SearchHit(**{**data, "updated_at": datetime.fromisoformat(data["updated_at"])})


@dataclass
class Item:
    """1 つの質問を 1 つの方式で解く途中の状態。

    Attributes:
        key: 「q01:agentic」のような ID。Batch API の custom_id にも使う。
        stage: 次に行う処理。analyze / expand / search / evaluate / answer / inquiry、
            終わったら done / error。
        data: 各段階の出力など、途中の結果。
    """

    key: str
    question_id: str
    mode: str
    stage: str
    data: dict
    usage: dict

    @property
    def question(self) -> dict:
        return self.data["question"]


# ---------- 1 問ずつの処理（Batch と同期の両方で使う） ----------


def _next_request(item: Item) -> tuple[Stage, str] | None:
    """item が次に AI に送るリクエスト（段階と入力）。AI を使わない段階なら None。"""
    q = item.question["question"]
    data = item.data
    hits = [_hit_from_dict(h) for h in data.get("hits", [])]
    analysis = Analysis(**data["analysis"]) if "analysis" in data else None
    match item.stage:
        case "analyze":
            return ANALYZE, agent.build_analyze_input(q, [])
        case "expand":
            previous = Evaluation(**data["evaluation"]) if "evaluation" in data else None
            return EXPAND, agent.build_expand_input(
                q, analysis, previous, data.get("used_queries", [])
            )
        case "evaluate":
            return EVALUATE, agent.build_evaluate_input(q, analysis, hits)
        case "answer":
            return ANSWER, agent.build_answer_input(q, hits, [])
        case "inquiry":
            department = data["inquiry_department"]
            return agent.inquiry_stage(department), agent.build_inquiry_input(
                q, _viewer(item.question), department, data.get("sources", []), data["unresolved"]
            )
    return None


def _apply_output(item: Item, output: Any) -> None:
    """AI の出力を item に反映し、次の段階に進める。"""
    data = item.data
    match item.stage:
        case "analyze":
            output.aspects = output.aspects[:MAX_ASPECTS]
            data["analysis"] = output.model_dump()
            if output.is_work_question:
                item.stage = "expand"
            else:
                _finish(item, NOT_WORK_CONTENT, [], "answered")
        case "expand":
            used = data.get("used_queries", [])
            data["queries"] = [q for q in output.queries if q not in used][:MAX_QUERIES]
            item.stage = "search"
        case "evaluate":
            data["evaluation"] = output.model_dump()
            data.setdefault("evaluations", []).append(output.model_dump())
            if output.sufficient or data["search_count"] > MAX_RESEARCH_COUNT:
                _prepare_answer(item)
            else:
                item.stage = "expand"
        case "answer":
            hits = [_hit_from_dict(h) for h in data["hits"]]
            content, sources = agent.build_sources(output, hits)
            status = output.status if sources else "not_found"
            _finish(item, content if sources else NOT_FOUND_CONTENT, sources, status)
            if status != "answered":
                analysis = Analysis(**data["analysis"]) if "analysis" in data else None
                data["inquiry_department"] = agent.choose_department(analysis, sources)
                data["unresolved"] = output.unresolved or [item.question["question"]]
                item.stage = "inquiry"
        case "inquiry":
            data["inquiry_suggestion"] = agent.inquiry_suggestion(
                output, data["inquiry_department"]
            )
            item.stage = "done"


def _prepare_answer(item: Item) -> None:
    if item.data["hits"]:
        item.stage = "answer"
        return
    # 根拠になる資料がないときは、チャットと同じく AI に回答を作らせない
    analysis = Analysis(**item.data["analysis"]) if "analysis" in item.data else None
    _finish(item, NOT_FOUND_CONTENT, [], "not_found")
    item.data["inquiry_department"] = agent.choose_department(analysis, [])
    item.data["unresolved"] = [item.question["question"]]
    item.stage = "inquiry"


def _finish(item: Item, content: str, sources: list[dict], status: str) -> None:
    item.data.update(content=content, sources=sources, answer_status=status)
    item.stage = "done"


def _run_search(item: Item) -> None:
    """検索は AI を使わない（埋め込みだけ）ので、その場で実行する。"""
    usage = Usage(**item.usage)
    queries = item.data.get("queries") or [item.question["question"]]
    new_hits = search_chunks(queries, _viewer(item.question), usage)
    item.usage = asdict(usage)
    current = [_hit_from_dict(h) for h in item.data.get("hits", [])]
    merged = agent.merge_hits(current, new_hits, limit=10)
    item.data["hits"] = [_hit_to_dict(h) for h in merged]
    item.data["retrieved"] = sorted(
        {*item.data.get("retrieved", []), *(f"{h.title}|{h.section}" for h in new_hits)}
    )
    item.data["used_queries"] = item.data.get("used_queries", []) + queries
    item.data["search_count"] = item.data.get("search_count", 0) + 1
    if item.mode == "basic":
        _prepare_answer(item)
    else:
        item.stage = "evaluate"


def _run_local_steps(items: list[Item]) -> None:
    for item in items:
        while item.stage == "search":
            _run_search(item)


# ---------- 実行の状態 ----------


@dataclass
class Run:
    """1 回の評価の実行。"""

    run_id: str
    items: list[Item]
    batch_id: str | None = None
    batch_keys: list[str] | None = None
    batches: int = 0

    @property
    def path(self) -> Path:
        return RUNS_DIR / self.run_id

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        state = {
            "run_id": self.run_id,
            "batch_id": self.batch_id,
            "batch_keys": self.batch_keys,
            "batches": self.batches,
            "items": [asdict(item) for item in self.items],
        }
        (self.path / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @classmethod
    def load(cls, run_id: str) -> "Run":
        path = RUNS_DIR / run_id / "state.json"
        if not path.exists():
            raise EvaluationError(f"評価の実行 {run_id} が見つかりません")
        state = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            run_id=state["run_id"],
            items=[Item(**item) for item in state["items"]],
            batch_id=state["batch_id"],
            batch_keys=state["batch_keys"],
            batches=state["batches"],
        )

    @property
    def is_finished(self) -> bool:
        return all(item.stage in ("done", "error") for item in self.items)


def create_run(modes: list[str], question_ids: list[str] | None = None) -> Run:
    """評価の実行を作る（まだ AI は呼ばない）。"""
    questions = load_questions(question_ids)
    if not questions:
        raise EvaluationError("評価する質問がありません")
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    items = [
        Item(
            key=f"{q['id']}:{mode}",
            question_id=q["id"],
            mode=mode,
            stage="analyze" if mode == "agentic" else "search",
            data={"question": q},
            usage=asdict(Usage()),
        )
        for q in questions
        for mode in modes
    ]
    return Run(run_id=run_id, items=items)


# ---------- Batch API ----------


def advance(run: Run) -> str:
    """Batch の結果を確認し、届いていれば反映して次の段階を送る。

    Returns:
        進み具合の説明（コマンドの出力に表示する）。
    """
    client = get_openai_client()
    if run.batch_id:
        batch = client.batches.retrieve(run.batch_id)
        if batch.status in ("validating", "in_progress", "finalizing"):
            done = batch.request_counts.completed if batch.request_counts else 0
            return f"Batch {run.batch_id} は処理中です（{batch.status}・{done} 件完了）"
        if batch.status != "completed":
            raise EvaluationError(f"Batch {run.batch_id} が {batch.status} で終了しました")
        _apply_batch_output(run, batch)
        run.batch_id, run.batch_keys = None, None

    _run_local_steps(run.items)
    requests = [(item, _next_request(item)) for item in run.items]
    requests = [(item, request) for item, request in requests if request is not None]
    if not requests:
        write_report(run)
        run.save()
        return f"評価が終わりました: {run.path / 'report.md'}"

    lines = []
    for item, (stage, user_input) in requests:
        body = build_request(stage, user_input)
        lines.append(
            json.dumps(
                {"custom_id": item.key, "method": "POST", "url": "/v1/responses", "body": body},
                ensure_ascii=False,
            )
        )
    upload = client.files.create(
        file=("requests.jsonl", BytesIO("\n".join(lines).encode())), purpose="batch"
    )
    batch = client.batches.create(
        input_file_id=upload.id, endpoint="/v1/responses", completion_window="24h"
    )
    run.batch_id = batch.id
    run.batch_keys = [item.key for item, _ in requests]
    run.batches += 1
    run.save()
    stages = sorted({item.stage for item, _ in requests})
    return f"Batch {batch.id} を送りました（{len(requests)} 件・段階: {', '.join(stages)}）"


def _apply_batch_output(run: Run, batch) -> None:
    by_key = {item.key: item for item in run.items}
    results: dict[str, dict] = {}
    client = get_openai_client()
    for file_id in (batch.output_file_id, batch.error_file_id):
        if not file_id:
            continue
        for line in client.files.content(file_id).text.splitlines():
            if line.strip():
                record = json.loads(line)
                results[record["custom_id"]] = record

    for key in run.batch_keys or []:
        item = by_key[key]
        record = results.get(key)
        response = (record or {}).get("response") or {}
        if not record or response.get("status_code") != 200:
            item.data["error"] = (
                f"{item.stage}: Batch の結果がありません（{record and record.get('error')}）"
            )
            item.stage = "error"
            continue
        stage, _ = _next_request(item)
        body = response["body"]
        usage = Usage(**item.usage)
        usage.add(
            body["model"], body["usage"]["input_tokens"], body["usage"]["output_tokens"], BATCH_RATE
        )
        item.usage = asdict(usage)
        try:
            _apply_output(item, parse_output(stage, _output_text(body)))
        except LLMError as e:
            item.data["error"] = str(e)
            item.stage = "error"


def _output_text(body: dict) -> str:
    """Responses API の応答（JSON）から、モデルが出力した文章を取り出す。"""
    texts = [
        content["text"]
        for output in body.get("output", [])
        if output.get("type") == "message"
        for content in output.get("content", [])
        if content.get("type") == "output_text"
    ]
    return "".join(texts)


# ---------- 同期の実行（回答時間を測る） ----------


def run_sync(run: Run) -> str:
    """1 問ずつチャットと同じ処理で実行する。料金は通常どおりかかるが、回答時間を測れる。"""
    for item in run.items:
        if item.stage in ("done", "error"):
            continue
        q = item.question
        try:
            generator = agent.run(q["question"], _viewer(q), [], item.mode)
            while True:
                try:
                    next(generator)
                except StopIteration as finished:
                    result = finished.value
                    break
        except Exception as e:  # 1 問の失敗で全体を止めない
            log.exception("%s: 失敗しました", item.key)
            item.data["error"] = f"{type(e).__name__}: {e}"
            item.stage = "error"
            continue
        retrieved = {
            f"{r['title']}|{r['section']}"
            for step in result.steps
            if step["type"] == "search"
            for r in step["results"]
        }
        item.data.update(
            content=result.content,
            sources=result.sources,
            answer_status=result.answer_status,
            inquiry_suggestion=result.inquiry_suggestion,
            search_count=result.search_count,
            duration_ms=result.duration_ms,
            retrieved=sorted(retrieved),
        )
        item.usage = asdict(result.usage)
        item.stage = "done"
        run.save()
    write_report(run)
    run.save()
    return f"評価が終わりました: {run.path / 'report.md'}"


# ---------- 採点と報告 ----------


def score_item(item: Item) -> dict:
    """自動で判定できる指標を計算する。

    回答の正確さ（expectedPoints）は、report.md を見て人が確認する。
    """
    q = item.question
    expected = {f"{s['title']}|{s['section']}" for s in q["expectedSources"]}
    cited = {f"{s['title']}|{s['section']}" for s in item.data.get("sources", [])}
    retrieved = set(item.data.get("retrieved", []))
    suggestion = item.data.get("inquiry_suggestion")
    expect_inquiry = q.get("expectInquiry")
    if expect_inquiry:
        inquiry_ok = bool(suggestion) and suggestion["department"] == expect_inquiry["department"]
    else:
        inquiry_ok = suggestion is None
    return {
        "retrievalRecall": len(expected & retrieved) / len(expected) if expected else None,
        "citationRecall": len(expected & cited) / len(expected) if expected else None,
        "inquiryCorrect": inquiry_ok,
        "error": item.data.get("error"),
    }


def write_report(run: Run) -> None:
    """結果を results.json（すべての値）と report.md（人が確認する表）に書き出す。"""
    rows = []
    for item in run.items:
        rows.append({"key": item.key, "mode": item.mode, **score_item(item), "usage": item.usage})
    (run.path / "results.json").write_text(
        json.dumps(
            {"items": [asdict(i) for i in run.items], "scores": rows}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )

    lines = [f"# 評価結果 {run.run_id}", "", "## 方式ごとの集計", ""]
    lines += [
        "| 方式 | 問題数 | 検索の再現率 | 引用の再現率 | 問い合わせ提案の正解率 "
        "| 平均費用（USD） | エラー |"
    ]
    lines += ["|---|---|---|---|---|---|---|"]
    for mode in MODES:
        scores = [r for r in rows if r["mode"] == mode]
        if not scores:
            continue
        lines.append(
            f"| {mode} | {len(scores)} | {_average(scores, 'retrievalRecall')} | "
            f"{_average(scores, 'citationRecall')} | {_average(scores, 'inquiryCorrect')} | "
            f"{_average_cost(scores)} | {sum(1 for r in scores if r['error'])} |"
        )
    lines += ["", "## 1 問ずつ（回答に含めるべき点を確認する）", ""]
    for item in run.items:
        q = item.question
        score = score_item(item)
        expected = ", ".join(f"{s['title']} {s['section']}" for s in q["expectedSources"])
        cited = ", ".join(
            f"{s['title']} {s['section'] or ''}" for s in item.data.get("sources", [])
        )
        inquiry = (item.data.get("inquiry_suggestion") or {}).get("department", "なし")
        lines += [
            f"### {item.key}（{q['type']}・{q['user']['department']}）{q['question']}",
            f"- 含めるべき点: {' / '.join(q['expectedPoints'])}",
            f"- 根拠の正解: {expected or 'なし'}",
            f"- 引用した資料: {cited or 'なし'}",
            f"- 問い合わせの提案: {inquiry}（{'正しい' if score['inquiryCorrect'] else '誤り'}）",
            "",
            item.data.get("content") or f"（エラー: {item.data.get('error')}）",
            "",
        ]
    (run.path / "report.md").write_text("\n".join(lines), encoding="utf-8")


def _average(rows: list[dict], key: str) -> str:
    values = [float(r[key]) for r in rows if r[key] is not None and not r["error"]]
    return f"{sum(values) / len(values):.0%}" if values else "-"


def _average_cost(rows: list[dict]) -> str:
    costs = [r["usage"]["cost_usd"] for r in rows if r["usage"]["cost_usd"] is not None]
    return f"{sum(costs) / len(costs):.4f}" if costs else "-"
