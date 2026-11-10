"""テストで OpenAI API の代わりに使う偽物。"""

from app.ai.embedding import EmbeddingResult
from app.models.document import EMBEDDING_DIMENSIONS

# 検索語やチャンクに含まれる言葉ごとに、ベクトルの向きを決める。
# 同じ言葉を含むものどうしが似たベクトルになり、本物の pgvector の検索をそのまま試せる
TOPICS = ["結婚", "経費", "パスワード", "評価", "休暇"]


def topic_vector(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for index, word in enumerate(TOPICS):
        if word in text:
            vector[index] = 1.0
    if not any(vector):
        vector[len(TOPICS)] = 1.0  # どの話題でもない
    return vector


def fake_embed_texts(texts: list[str]) -> EmbeddingResult:
    return EmbeddingResult(vectors=[topic_vector(t) for t in texts], total_tokens=10 * len(texts))


class ScriptedLLM:
    """段階の名前ごとに、決めておいた出力を順に返す。

    Attributes:
        calls: 呼ばれた段階の名前と入力。
    """

    def __init__(self, outputs: dict[str, list]) -> None:
        self.outputs = {name: list(values) for name, values in outputs.items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, stage, user_input, usage):
        self.calls.append((stage.name, user_input))
        usage.add("gpt-6.1-sol", 100, 50)
        values = self.outputs[stage.name]
        return values.pop(0) if len(values) > 1 else values[0]

    def called(self, name: str) -> int:
        return sum(1 for stage, _ in self.calls if stage == name)
