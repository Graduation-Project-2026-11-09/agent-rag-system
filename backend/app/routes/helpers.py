"""API の共通処理。"""

from datetime import UTC, date, datetime

from flask import jsonify, request


class BadRequest(Exception):
    """リクエストの内容が正しくない。メッセージは画面にそのまま表示する。"""


def json_body() -> dict:
    """リクエストの JSON。JSON でない場合は空の辞書。"""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def error(message: str, status: int):
    """docs/api-spec.md のエラーの形（{ message }）で返す。"""
    return jsonify(message=message), status


def required_text(data: dict, key: str, label: str, max_length: int) -> str:
    """必須の文字列を取り出す。

    Raises:
        BadRequest: 空、または長すぎる場合。
    """
    value = str(data.get(key) or "").strip()
    if not value:
        raise BadRequest(f"{label}を入力してください")
    if len(value) > max_length:
        raise BadRequest(f"{label}は {max_length} 文字以内で入力してください")
    return value


def parse_datetime(value: str | None) -> datetime | None:
    """画面から送られる ISO 8601 の日時を読む。タイムゾーンがなければ UTC とみなす。

    Raises:
        BadRequest: 日時の形式が正しくない場合。
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        raise BadRequest(f"日時の形式が正しくありません: {value}") from e
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_date(value: str | None) -> date | None:
    """YYYY-MM-DD の日付を読む。

    Raises:
        BadRequest: 日付の形式が正しくない場合。
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise BadRequest(f"日付の形式が正しくありません: {value}") from e


def string_list(value, label: str) -> list[str]:
    """文字列のリストを取り出す（空の要素は除く）。

    Raises:
        BadRequest: リストでない場合。
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise BadRequest(f"{label}の形式が正しくありません")
    return [str(v).strip() for v in value if str(v).strip()]


def departments_target(value, label: str) -> list[str]:
    """{ type: "all" } / { type: "departments", departments: [...] } を部署のリストにする。

    Returns:
        部署のリスト。全員が対象なら空のリスト。

    Raises:
        BadRequest: 形式が正しくない、または部署が 1 つも指定されていない場合。
    """
    from ..masters import DEPARTMENTS

    if not isinstance(value, dict) or value.get("type") not in ("all", "departments"):
        raise BadRequest(f"{label}の指定が正しくありません")
    if value["type"] == "all":
        return []
    departments = string_list(value.get("departments"), label)
    if not departments:
        raise BadRequest(f"{label}の部署を 1 つ以上選択してください")
    unknown = [d for d in departments if d not in DEPARTMENTS]
    if unknown:
        raise BadRequest(f"存在しない部署です: {'、'.join(unknown)}")
    return departments
