import json
from types import SimpleNamespace

import pytest

from app.ai import llm
from app.ai.agent import ANSWER, Answer
from app.ai.llm import JsonStringFieldReader, LLMError, Usage


def _read_in_pieces(output: str, size: int) -> str:
    reader = JsonStringFieldReader("content")
    return "".join(reader.feed(output[i : i + size]) for i in range(0, len(output), size))


@pytest.mark.parametrize("size", [1, 2, 3, 7, 1000])
def test_reader_returns_the_value_however_the_output_is_split(size):
    content = '結婚休暇は **5日** です [1]。\n- 「申請」は "勤怠" から\\ 😀'
    output = json.dumps({"content": content, "cited": [1], "status": "answered"}, ensure_ascii=True)

    assert _read_in_pieces(output, size) == content


def test_reader_returns_nothing_when_the_field_is_not_first():
    output = json.dumps({"cited": [1], "content": "本文"}, ensure_ascii=False)

    assert _read_in_pieces(output, 3) == ""


class FakeStreamClient:
    """Responses API のストリーミングの代わりに、決めておいたイベントを返す。"""

    def __init__(self, events):
        self.responses = SimpleNamespace(create=lambda **request: iter(events))


def _events(output: str, finished: str = "response.completed"):
    deltas = [
        SimpleNamespace(type="response.output_text.delta", delta=output[i : i + 5])
        for i in range(0, len(output), 5)
    ]
    usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    return [*deltas, SimpleNamespace(type=finished, response=SimpleNamespace(usage=usage))]


def _run(stream):
    pieces = []
    while True:
        try:
            pieces.append(next(stream))
        except StopIteration as finished:
            return pieces, finished.value


def test_stream_structured_yields_content_and_returns_output(app, monkeypatch):
    expected = Answer(
        content="締め日は **毎月末日** です [1]。", cited=[1], status="answered", unresolved=[]
    )
    client = FakeStreamClient(_events(expected.model_dump_json()))
    monkeypatch.setattr(llm, "get_openai_client", lambda: client)
    usage = Usage()

    with app.app_context():
        pieces, output = _run(llm.stream_structured(ANSWER, "質問", usage, field="content"))

    assert len(pieces) > 1  # 一度にではなく、少しずつ届く
    assert "".join(pieces) == expected.content
    assert output == expected
    assert usage.input_tokens == 100


def test_stream_structured_fails_when_response_is_cut_off(app, monkeypatch):
    client = FakeStreamClient(_events('{"content": "途中', finished="response.incomplete"))
    monkeypatch.setattr(llm, "get_openai_client", lambda: client)

    with app.app_context(), pytest.raises(LLMError):
        _run(llm.stream_structured(ANSWER, "質問", Usage(), field="content"))
