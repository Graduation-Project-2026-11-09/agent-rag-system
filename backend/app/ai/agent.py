"""検索Agent（Agentic RAG）と、比較用の通常の RAG。

検索Agent の流れ（docs/architecture/ai.md）:
    ① 質問分析 → ② 検索語の展開 → ③ 検索 → ④ 充足度の評価
    → 足りなければ ② に戻る（再検索は最大 1 回）→ ⑤ 回答の作成 → 必要なら問い合わせの下書き

各段階の入力を作る関数（build_*）と、出力を処理する関数を分けているのは、
評価で同じ処理を Batch API でも実行できるようにするため（app/evaluation.py）。
"""

import re
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from ..extensions import db
from ..masters import DEPARTMENTS
from . import prompts
from .llm import Stage, Usage, call_structured, to_prompt_json
from .retrieval import SearchHit, Viewer, count_visible_documents, search_chunks

# OpenAI API の料金と回答時間を抑えるため、再検索は最大 1 回まで（計画書では 3 回。ai.md 参照）
MAX_RESEARCH_COUNT = 1
# 会話の履歴は直近のものだけを渡す。長い履歴は費用が増えるうえ、古い話題に引きずられるため
HISTORY_LIMIT = 4
HISTORY_CHARS = 400
# 資料が見つからなかったときの回答。根拠のない回答をしないよう、AI には作らせない（ルール 6）
NOT_FOUND_CONTENT = (
    "閲覧できる社内資料の中に、この質問に答えられる情報が見つかりませんでした。\n\n"
    "誤った案内を避けるため、推測での回答は控えます。担当部署への問い合わせをおすすめします。"
)
NOT_WORK_CONTENT = (
    "社内ナビAIは、社内の制度や手続きについての質問にお答えしています。"
    "就業規則・休暇・経費精算・PC の使い方など、お仕事に関することを質問してください。"
)
# 回答でこの部署が分からないときの問い合わせ先
FALLBACK_DEPARTMENT = "総務部"


# 件数の制約（観点は 5 個までなど）は指示で伝える。JSON Schema の minItems などは
# モデルによって使えないことがあるため、スキーマには入れずにコード側で切り詰める
MAX_ASPECTS = 5
MAX_QUERIES = 5


class Analysis(BaseModel):
    intent: str
    aspects: list[str]
    department: str
    is_work_question: bool


class Expansion(BaseModel):
    queries: list[str]
    strategy: str


class Evaluation(BaseModel):
    sufficient: bool
    covered: list[str]
    missing: list[str]
    reason: str


class NextStep(BaseModel):
    title: str
    description: str
    department: str
    deadline: str


class Answer(BaseModel):
    content: str
    cited: list[int]
    status: Literal["answered", "partial", "not_found"]
    next_steps: list[NextStep]
    unresolved: list[str]


class InquiryDraft(BaseModel):
    subject: str
    body: str
    reason: str


ANALYZE = Stage(
    "analyze",
    "AI_MODEL_ANALYZE",
    prompts.ANALYZE.replace("{departments}", "、".join(DEPARTMENTS)),
    Analysis,
)
EXPAND = Stage("expand", "AI_MODEL_EXPAND", prompts.EXPAND, Expansion)
EVALUATE = Stage("evaluate", "AI_MODEL_EVALUATE", prompts.EVALUATE, Evaluation, "medium")
ANSWER = Stage("answer", "AI_MODEL_ANSWER", prompts.ANSWER, Answer, "medium")
INQUIRY = Stage("inquiry", "AI_MODEL_INQUIRY", prompts.INQUIRY, InquiryDraft)


@dataclass
class HistoryItem:
    """会話の履歴の 1 件。"""

    role: str
    content: str


@dataclass
class AgentResult:
    """回答の結果。Message の各カラムに保存する。

    Attributes:
        answer_status: answered / partial / not_found。利用履歴の「回答不可」の判定に使う。
        mode: agentic（検索Agent）/ basic（通常の RAG）。
    """

    content: str
    steps: list[dict]
    search_count: int
    duration_ms: int
    sources: list[dict]
    next_steps: list[dict]
    inquiry_suggestion: dict | None
    answer_status: str
    mode: str
    usage: Usage = field(default_factory=Usage)


class _StepRecorder:
    """画面に表示する処理の過程（SSE の step イベント）を作る。"""

    def __init__(self) -> None:
        self.steps: list[dict] = []

    def add(self, step_type: str, title: str, **fields) -> dict:
        step = {"id": f"s{len(self.steps) + 1}", "type": step_type, "title": title}
        step.update({k: v for k, v in fields.items() if v is not None})
        self.steps.append(step)
        return step


# ---------- 各段階の入力 ----------


def _format_history(history: list[HistoryItem]) -> str:
    if not history:
        return "（なし）"
    lines = []
    for item in history[-HISTORY_LIMIT:]:
        speaker = "従業員" if item.role == "user" else "社内ナビAI"
        lines.append(f"{speaker}: {item.content[:HISTORY_CHARS]}")
    return "\n".join(lines)


def _format_hits(hits: list[SearchHit]) -> str:
    blocks = []
    for number, hit in enumerate(hits, start=1):
        heading = f"[{number}] {hit.title}"
        if hit.section:
            heading += f" / {hit.section}"
        blocks.append(f"{heading}\n{hit.content}")
    return "\n\n".join(blocks) if blocks else "（見つかった資料はありません）"


def build_analyze_input(question: str, history: list[HistoryItem]) -> str:
    return f"## これまでの会話\n{_format_history(history)}\n\n## 質問\n{question}"


def build_expand_input(
    question: str, analysis: Analysis, previous: Evaluation | None, used_queries: list[str]
) -> str:
    text = (
        f"## 質問\n{question}\n\n## 意図\n{analysis.intent}\n\n"
        f"## 観点\n{to_prompt_json(analysis.aspects)}"
    )
    if previous is not None:
        text += (
            f"\n\n## 前回の検索で足りなかった情報\n{to_prompt_json(previous.missing)}"
            f"\n\n## 前回使った検索語\n{to_prompt_json(used_queries)}"
        )
    return text


def build_evaluate_input(question: str, analysis: Analysis, hits: list[SearchHit]) -> str:
    return (
        f"## 質問\n{question}\n\n## 観点\n{to_prompt_json(analysis.aspects)}\n\n"
        f"## 社内資料の抜粋\n{_format_hits(hits)}"
    )


def build_answer_input(question: str, hits: list[SearchHit], history: list[HistoryItem]) -> str:
    return (
        f"## これまでの会話\n{_format_history(history)}\n\n## 質問\n{question}\n\n"
        f"## 社内資料の抜粋\n{_format_hits(hits)}"
    )


def build_inquiry_input(
    question: str, viewer: Viewer, department: str, sources: list[dict], unresolved: list[str]
) -> str:
    checked = [f"{s['title']} {s['section'] or ''}".strip() for s in sources]
    return (
        f"## 宛先の部署\n{department}\n\n## 質問者\n{viewer.department}の{viewer.name}\n\n"
        f"## 質問\n{question}\n\n## 確認済みの社内資料\n{to_prompt_json(checked)}\n\n"
        f"## 資料では分からなかったこと\n{to_prompt_json(unresolved)}"
    )


def inquiry_stage(department: str) -> Stage:
    """宛先の部署を指示に入れた、問い合わせの下書きの段階。"""
    return Stage(
        INQUIRY.name,
        INQUIRY.model_config_key,
        INQUIRY.instructions.replace("{department}", department),
        InquiryDraft,
    )


# ---------- 出力の処理 ----------


def merge_hits(current: list[SearchHit], new: list[SearchHit], limit: int) -> list[SearchHit]:
    """再検索の結果を前回の結果とまとめる（同じチャンクは類似度の高い方を残す）。"""
    best = {hit.chunk_id: hit for hit in current}
    for hit in new:
        if hit.chunk_id not in best or best[hit.chunk_id].score < hit.score:
            best[hit.chunk_id] = hit
    return sorted(best.values(), key=lambda hit: hit.score, reverse=True)[:limit]


def build_sources(answer: Answer, hits: list[SearchHit]) -> tuple[str, list[dict]]:
    """回答で引用された抜粋だけを根拠資料にし、本文の番号を 1 から振り直す。

    AI が存在しない番号を書いた場合は、その番号を本文から消す（根拠のない引用を表示しないため）。

    Returns:
        番号を振り直した本文と、根拠資料のリスト（docs/api-spec.md の sources の形）。
    """
    cited_in_text = [int(n) for n in re.findall(r"\[(\d+)\]", answer.content)]
    order = []
    for number in [*cited_in_text, *answer.cited]:
        if 1 <= number <= len(hits) and number not in order:
            order.append(number)
    renumber = {old: new for new, old in enumerate(order, start=1)}

    def replace(match: re.Match) -> str:
        new = renumber.get(int(match.group(1)))
        return f"[{new}]" if new else ""

    content = re.sub(r"\[(\d+)\]", replace, answer.content)
    sources = []
    for old in order:
        hit = hits[old - 1]
        sources.append(
            {
                "index": renumber[old],
                "documentId": str(hit.document_id),
                "title": hit.title,
                "fileType": hit.file_type,
                "department": hit.department,
                "updatedAt": hit.updated_at.isoformat(),
                "section": hit.section,
                "page": hit.page,
                "excerpt": hit.content,
            }
        )
    return content, sources


def next_steps_to_dicts(answer: Answer) -> list[dict]:
    return [
        {
            "id": f"t{number}",
            "title": step.title,
            "description": step.description,
            "department": step.department or None,
            "deadline": step.deadline or None,
        }
        for number, step in enumerate(answer.next_steps, start=1)
    ]


def choose_department(analysis: Analysis | None, sources: list[dict]) -> str:
    """問い合わせ先の部署を決める。分析の結果を優先し、なければ根拠資料の部署にする。"""
    if analysis is not None and analysis.department in DEPARTMENTS:
        return analysis.department
    if sources:
        return sources[0]["department"]
    return FALLBACK_DEPARTMENT


def inquiry_suggestion(draft: InquiryDraft, department: str) -> dict:
    return {
        "department": department,
        "reason": draft.reason,
        "subject": draft.subject,
        "body": draft.body,
    }


# ---------- 実行 ----------


def run_agentic(
    question: str, viewer: Viewer, history: list[HistoryItem]
) -> Generator[dict, None, AgentResult]:
    """検索Agent で回答する。処理の過程を 1 段階ずつ yield し、最後に結果を返す。

    Args:
        question: 利用者の質問。
        viewer: 質問した利用者。閲覧できる資料の判定に使う。
        history: これまでの会話。

    Yields:
        画面に表示する処理の過程（docs/api-spec.md の step）。

    Returns:
        回答の結果。

    Raises:
        LLMError: AI の呼び出しに失敗した場合。
        EmbeddingError: 検索語のベクトル化に失敗した場合。
    """
    started = time.monotonic()
    usage = Usage()
    recorder = _StepRecorder()
    visible_count = count_visible_documents(viewer)
    db.session.rollback()  # AI の応答を待つ間にトランザクションを開いたままにしない

    analysis = call_structured(ANALYZE, build_analyze_input(question, history), usage)
    analysis.aspects = analysis.aspects[:MAX_ASPECTS]
    yield recorder.add(
        "analyze", "質問内容を分析", detail=f"意図：{analysis.intent}", items=analysis.aspects
    )
    if not analysis.is_work_question:
        yield recorder.add(
            "generate", "回答を作成", detail="社内の制度や手続きに関する質問ではありません"
        )
        return _result(NOT_WORK_CONTENT, recorder, 0, started, [], [], None, "answered", usage)

    hits: list[SearchHit] = []
    used_queries: list[str] = []
    evaluation: Evaluation | None = None
    search_count = 0
    while True:
        expansion = call_structured(
            EXPAND, build_expand_input(question, analysis, evaluation, used_queries), usage
        )
        queries = [q for q in expansion.queries if q not in used_queries][:MAX_QUERIES]
        if search_count == 0:
            yield recorder.add(
                "plan",
                "検索戦略を決定",
                detail=f"{expansion.strategy}（閲覧可能な資料 {visible_count} 件が対象）",
                queries=queries,
            )
        new_hits = search_chunks(queries, viewer, usage)
        used_queries += queries
        search_count += 1
        hits = merge_hits(hits, new_hits, limit=10)
        yield recorder.add(
            "search",
            "社内資料を検索（1回目）" if search_count == 1 else f"追加検索（{search_count}回目）",
            # 1 回目の検索語は「検索戦略」に表示済みのため、追加検索のときだけ載せる
            queries=queries if search_count > 1 else None,
            results=[hit.to_step_result() for hit in new_hits],
        )

        evaluation = call_structured(
            EVALUATE, build_evaluate_input(question, analysis, hits), usage
        )
        yield recorder.add(
            "evaluate",
            "情報の充足度を評価：十分" if evaluation.sufficient else "情報の充足度を評価：不足あり",
            detail=evaluation.reason,
            sufficient=evaluation.sufficient,
        )
        if evaluation.sufficient or search_count > MAX_RESEARCH_COUNT:
            break

    result = yield from _answer(question, viewer, history, hits, analysis, recorder, usage)
    return _result(
        result[0], recorder, search_count, started, *result[1:], usage=usage, mode="agentic"
    )


def run_basic(
    question: str, viewer: Viewer, history: list[HistoryItem]
) -> Generator[dict, None, AgentResult]:
    """通常の RAG（質問文で 1 回検索して回答する）。検索Agent との比較に使う。

    引数・戻り値・例外は run_agentic() と同じ。
    """
    started = time.monotonic()
    usage = Usage()
    recorder = _StepRecorder()
    hits = search_chunks([question], viewer, usage)
    yield recorder.add(
        "search", "社内資料を検索（1回目）", results=[hit.to_step_result() for hit in hits]
    )
    result = yield from _answer(question, viewer, history, hits, None, recorder, usage)
    return _result(result[0], recorder, 1, started, *result[1:], usage=usage, mode="basic")


def _answer(
    question: str,
    viewer: Viewer,
    history: list[HistoryItem],
    hits: list[SearchHit],
    analysis: Analysis | None,
    recorder: _StepRecorder,
    usage: Usage,
) -> Generator[dict, None, tuple]:
    if not hits:
        # 根拠になる資料がないときは、AI に回答を作らせない（推測で答えさせないため）
        department = choose_department(analysis, [])
        suggestion = _draft_inquiry(question, viewer, department, [], [question], usage)
        yield recorder.add(
            "generate", "回答を作成", detail="根拠となる資料がないため、推測での回答は行いません"
        )
        return NOT_FOUND_CONTENT, [], [], suggestion, "not_found"

    answer = call_structured(ANSWER, build_answer_input(question, hits, history), usage)
    content, sources = build_sources(answer, hits)
    status = answer.status if sources else "not_found"
    if not sources:
        content = NOT_FOUND_CONTENT

    suggestion = None
    if status != "answered":
        department = choose_department(analysis, sources)
        unresolved = answer.unresolved or [question]
        suggestion = _draft_inquiry(question, viewer, department, sources, unresolved, usage)

    detail = (
        f"根拠資料 {len(sources)} 件をもとに回答を作成しました"
        if sources
        else "根拠となる資料がないため、推測での回答は行いません"
    )
    yield recorder.add("generate", "回答を作成", detail=detail)
    return content, sources, next_steps_to_dicts(answer) if sources else [], suggestion, status


def _draft_inquiry(
    question: str,
    viewer: Viewer,
    department: str,
    sources: list[dict],
    unresolved: list[str],
    usage: Usage,
) -> dict:
    draft = call_structured(
        inquiry_stage(department),
        build_inquiry_input(question, viewer, department, sources, unresolved),
        usage,
    )
    return inquiry_suggestion(draft, department)


def _result(
    content: str,
    recorder: _StepRecorder,
    search_count: int,
    started: float,
    sources: list[dict],
    next_steps: list[dict],
    suggestion: dict | None,
    answer_status: str,
    usage: Usage,
    mode: str = "agentic",
) -> AgentResult:
    return AgentResult(
        content=content,
        steps=recorder.steps,
        search_count=search_count,
        duration_ms=int((time.monotonic() - started) * 1000),
        sources=sources,
        next_steps=next_steps,
        inquiry_suggestion=suggestion,
        answer_status=answer_status,
        mode=mode,
        usage=usage,
    )


def run(
    question: str, viewer: Viewer, history: list[HistoryItem], mode: str
) -> Generator[dict, None, AgentResult]:
    """設定の方式（agentic / basic）で回答する。"""
    runner = run_basic if mode == "basic" else run_agentic
    return (yield from runner(question, viewer, history))
