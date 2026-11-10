"""OpenAI API のクライアント。"""

from flask import current_app
from openai import OpenAI

# 応答が遅いときに worker や API が待ち続けないよう、1 回の呼び出しの上限を決める
REQUEST_TIMEOUT_SEC = 60
# 一時的なエラー（429・5xx）は SDK が待ってから自動でやり直す
MAX_RETRIES = 3


class AIConfigError(Exception):
    """OpenAI API を使うための設定が足りない。"""


def get_openai_client() -> OpenAI:
    """設定の API キーで OpenAI のクライアントを作る。

    Returns:
        OpenAI のクライアント。

    Raises:
        AIConfigError: OPENAI_API_KEY が設定されていない場合。
    """
    api_key = current_app.config["OPENAI_API_KEY"]
    if not api_key:
        raise AIConfigError("OPENAI_API_KEY が設定されていません")
    return OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SEC, max_retries=MAX_RETRIES)
