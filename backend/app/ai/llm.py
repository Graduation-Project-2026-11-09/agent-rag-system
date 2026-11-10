"""OpenAI の Responses API で、決まった形（JSON Schema）の出力を受け取る。

リクエストの組み立て（build_request）と呼び出し（call_structured）を分けているのは、
評価で同じリクエストを Batch API に送れるようにするため。
"""

import json
from dataclasses import dataclass
from typing import Any

from flask import current_app
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from .client import get_openai_client

# 料金（USD / 100 万トークン、Standard）。2026-11-10 に公式の料金ページで確認した値。
# 利用履歴に費用の目安を出すために使う。載っていないモデルは費用を計算しない
PRICES_PER_MILLION = {
    "gpt-6-astra": (10.00, 50.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6-luna": (0.10, 0.50),
    "text-embedding-3-large": (0.13, 0.0),
}


class LLMError(Exception):
    """OpenAI API の呼び出し、または出力の読み取りに失敗した。"""


@dataclass
class Usage:
    """1 回以上の呼び出しで使ったトークン数。

    Attributes:
        input_tokens: 入力のトークン数。
        output_tokens: 出力のトークン数（推論のトークンを含む）。
        cost_usd: 費用の目安。料金が分からないモデルを含む場合は None。
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0

    def add(self, model: str, input_tokens: int, output_tokens: int, rate: float = 1.0) -> None:
        """呼び出し 1 回分を加える。

        Args:
            model: 使ったモデル。
            input_tokens: 入力のトークン数。
            output_tokens: 出力のトークン数。
            rate: 料金の倍率。Batch API は半額なので 0.5。
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        price = PRICES_PER_MILLION.get(model)
        if price is None or self.cost_usd is None:
            self.cost_usd = None
        else:
            cost = (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
            self.cost_usd += cost * rate


@dataclass
class Stage:
    """エージェントの 1 つの段階（質問分析・回答の作成など）の設定。

    Attributes:
        name: 段階の名前。ログと Batch API の custom_id に使う。
        model_config_key: 使うモデル名が入っている設定のキー（例: AI_MODEL_ANSWER）。
        instructions: システムへの指示（プロンプト）。
        output: 出力の形。
        reasoning_effort: 推論の量。多いほど精度は上がるが、時間と費用がかかる。
    """

    name: str
    model_config_key: str
    instructions: str
    output: type[BaseModel]
    reasoning_effort: str = "low"


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic のモデルを、構造化出力の strict モードで使える JSON Schema にする。

    strict モードでは、すべてのプロパティを required にし、
    additionalProperties を false にする必要があるため。
    """

    def fix(node: Any) -> Any:
        if isinstance(node, list):
            return [fix(v) for v in node]
        if not isinstance(node, dict):
            return node
        result = {}
        for key, value in node.items():
            if key in ("title", "default"):
                continue  # strict モードでは使えない注釈
            if key in ("properties", "$defs"):
                # ここのキーはプロパティ名・型名なので、「title」という名前でも消さない
                result[key] = {name: fix(schema) for name, schema in value.items()}
            else:
                result[key] = fix(value)
        if result.get("type") == "object" and "properties" in result:
            result["required"] = list(result["properties"])
            result["additionalProperties"] = False
        return result

    return fix(model.model_json_schema())


def build_request(stage: Stage, user_input: str) -> dict[str, Any]:
    """Responses API に送るリクエストの本体を作る。

    Args:
        stage: 段階の設定。
        user_input: 質問や検索結果などをまとめた入力。

    Returns:
        client.responses.create() の引数、または Batch API の body にそのまま使える辞書。
    """
    return {
        "model": current_app.config[stage.model_config_key],
        "instructions": stage.instructions,
        "input": user_input,
        "reasoning": {"effort": stage.reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": stage.output.__name__,
                "schema": strict_json_schema(stage.output),
                "strict": True,
            }
        },
        # 社内資料の内容を OpenAI 側に保存させない
        "store": False,
    }


def parse_output(stage: Stage, output_text: str) -> BaseModel:
    """モデルの出力（JSON の文字列）を、段階の出力の形として読み取る。

    Raises:
        LLMError: 出力が決まった形になっていない場合。
    """
    try:
        return stage.output.model_validate_json(output_text)
    except ValidationError as e:
        raise LLMError(f"{stage.name}: AI の出力を読み取れませんでした") from e


def call_structured(stage: Stage, user_input: str, usage: Usage) -> BaseModel:
    """段階を 1 回実行し、決まった形の出力を返す。

    Args:
        stage: 段階の設定。
        user_input: 入力。
        usage: 使ったトークン数を加える先。

    Returns:
        stage.output の形の出力。

    Raises:
        LLMError: API の呼び出しか、出力の読み取りに失敗した場合。
        AIConfigError: API キーが設定されていない場合。
    """
    request = build_request(stage, user_input)
    try:
        response = get_openai_client().responses.create(**request)
    except OpenAIError as e:
        raise LLMError(f"{stage.name}: AI の呼び出しに失敗しました（{type(e).__name__}）") from e

    if response.usage is not None:
        usage.add(request["model"], response.usage.input_tokens, response.usage.output_tokens)
    return parse_output(stage, response.output_text)


def to_prompt_json(value: Any) -> str:
    """入力に埋め込む値を、読みやすい JSON にする（日本語をエスケープしない）。"""
    return json.dumps(value, ensure_ascii=False, indent=2)
