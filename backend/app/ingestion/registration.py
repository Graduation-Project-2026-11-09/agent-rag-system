"""資料の登録。原本を保存して取り込み待ちにする（取り込み自体は worker が行う）。"""

import uuid
from collections.abc import Sequence
from datetime import date

from ..extensions import db
from ..models import Document, DocumentVersion, User
from ..models.document import VISIBILITY_TYPES
from ..storage import get_storage
from .extract import ExtractionError, file_type_from_name


class RegistrationError(Exception):
    """登録する資料の内容が正しくない。メッセージは画面にそのまま表示する。"""


def register_document(
    file_name: str,
    data: bytes,
    *,
    title: str,
    department: str,
    category: str | None = None,
    visibility_type: str = "all",
    visible_departments: Sequence[str] = (),
    tags: Sequence[str] = (),
    effective_date: date | None = None,
    note: str | None = None,
    uploaded_by: User | None = None,
) -> Document:
    """新しい資料（版 1）を登録し、取り込み待ち（status=processing）にする。

    資料管理画面のアップロード API と、開発用の flask import-document から使う。

    Args:
        file_name: 元のファイル名。拡張子で形式を判定する。
        data: ファイルの内容。
        title: 資料名。
        department: 資料を管理する部署。
        category: 資料の分類。
        visibility_type: all（全員）/ departments（visible_departments の部署だけ）。
        visible_departments: 閲覧できる部署。visibility_type が departments のときに必須。
        tags: 検索の補助に使うタグ。
        effective_date: 施行日。
        note: 版の説明（例: 2026年4月改定）。
        uploaded_by: 登録した利用者。

    Returns:
        登録した資料。

    Raises:
        RegistrationError: 形式が対応していない、または公開範囲の指定が正しくない場合。
    """
    try:
        file_type = file_type_from_name(file_name)
    except ExtractionError as e:
        raise RegistrationError(str(e)) from e
    if not data:
        raise RegistrationError("ファイルが空です")
    if visibility_type not in VISIBILITY_TYPES:
        raise RegistrationError(f"公開範囲の指定が正しくありません: {visibility_type}")
    if visibility_type == "departments" and not visible_departments:
        # 部署を指定せずに部署限定にすると、誰も検索できない資料になるため
        raise RegistrationError("部署限定の資料は、閲覧できる部署を1つ以上指定してください")

    document = Document(
        title=title,
        category=category,
        department=department,
        visibility_type=visibility_type,
        visible_departments=list(visible_departments) if visibility_type == "departments" else [],
        tags=list(tags),
        status="processing",
        processing_stage="uploaded",
        current_version=1,
    )
    db.session.add(document)
    db.session.flush()  # 保存先のキーに資料の id を使うため

    # 日本語や記号を含むファイル名をキーに使うと扱いにくいため、ランダムな名前で保存する
    storage_key = f"documents/{document.id}/v1/{uuid.uuid4().hex}.{file_type}"
    db.session.add(
        DocumentVersion(
            document=document,
            version=1,
            file_name=file_name,
            file_type=file_type,
            size=len(data),
            storage_key=storage_key,
            effective_date=effective_date,
            note=note,
            uploaded_by_id=uploaded_by.id if uploaded_by else None,
        )
    )
    get_storage().save(storage_key, data)
    db.session.commit()
    return document
