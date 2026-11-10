"""テキストのベクトル化（埋め込み）。資料の取り込みと、質問の検索の両方で使う。"""

from dataclasses import dataclass

from flask import current_app
from openai import OpenAIError

from ..models.document import EMBEDDING_DIMENSIONS
from .client import get_openai_client

# 1 回の API 呼び出しで送るテキストの数。呼び出し回数を減らしつつ、
# 1 リクエストのトークン数の上限を超えないようにする（チャンクは最大 800 字程度）
BATCH_SIZE = 100


class EmbeddingError(Exception):
    """OpenAI API でのベクトル化に失敗した。"""


@dataclass
class EmbeddingResult:
    """ベクトル化の結果。

    Attributes:
        vectors: 入力と同じ順番のベクトル。
        total_tokens: 使ったトークン数。料金の確認に使う。
    """

    vectors: list[list[float]]
    total_tokens: int


def embed_texts(texts: list[str]) -> EmbeddingResult:
    """テキストをまとめてベクトルに変換する。

    Args:
        texts: ベクトルにするテキスト。

    Returns:
        入力と同じ順番のベクトルと、使ったトークン数。

    Raises:
        EmbeddingError: OpenAI API の呼び出しに失敗した場合（自動のやり直しの後も失敗したとき）。
    """
    client = get_openai_client()
    model = current_app.config["AI_EMBEDDING_MODEL"]
    vectors: list[list[float]] = []
    total_tokens = 0

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        try:
            response = client.embeddings.create(
                model=model, input=batch, dimensions=EMBEDDING_DIMENSIONS
            )
        except OpenAIError as e:
            raise EmbeddingError(f"ベクトル化に失敗しました（{type(e).__name__}）") from e
        # 応答の順番は保証されていないため、index で並べ直す
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        total_tokens += response.usage.total_tokens

    return EmbeddingResult(vectors=vectors, total_tokens=total_tokens)
