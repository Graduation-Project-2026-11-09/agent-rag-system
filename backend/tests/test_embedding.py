from types import SimpleNamespace

import openai
import pytest

from app.ai import embedding
from app.ai.client import AIConfigError, get_openai_client
from app.ai.embedding import EmbeddingError, embed_texts
from app.models.document import EMBEDDING_DIMENSIONS


class _FakeEmbeddings:
    def __init__(self):
        self.requests = []

    def create(self, model, input, dimensions):
        self.requests.append({"model": model, "input": input, "dimensions": dimensions})
        # 順番が入れ替わって返ってきても、index で並べ直されることを確かめる
        data = [
            SimpleNamespace(index=i, embedding=[float(len(text))]) for i, text in enumerate(input)
        ]
        return SimpleNamespace(
            data=list(reversed(data)), usage=SimpleNamespace(total_tokens=len(input))
        )


@pytest.fixture
def fake_client(monkeypatch):
    client = SimpleNamespace(embeddings=_FakeEmbeddings())
    monkeypatch.setattr(embedding, "get_openai_client", lambda: client)
    return client


def test_embed_texts_in_batches(app, fake_client, monkeypatch):
    monkeypatch.setattr(embedding, "BATCH_SIZE", 2)
    result = embed_texts(["a", "bb", "ccc"])

    assert result.vectors == [[1.0], [2.0], [3.0]]
    assert result.total_tokens == 3
    requests = fake_client.embeddings.requests
    assert [r["input"] for r in requests] == [["a", "bb"], ["ccc"]]
    assert all(r["model"] == "text-embedding-3-large" for r in requests)
    assert all(r["dimensions"] == EMBEDDING_DIMENSIONS for r in requests)


def test_embed_texts_wraps_api_error(app, fake_client):
    class APITimeoutError(openai.OpenAIError):
        """SDK の版によって作り方が変わるため、OpenAIError を継承した例外で代わりにする。"""

    def fail(**kwargs):
        raise APITimeoutError("timeout")

    fake_client.embeddings.create = fail
    with pytest.raises(EmbeddingError, match="APITimeoutError"):
        embed_texts(["a"])


def test_client_requires_api_key(app):
    app.config["OPENAI_API_KEY"] = ""
    with pytest.raises(AIConfigError):
        get_openai_client()
