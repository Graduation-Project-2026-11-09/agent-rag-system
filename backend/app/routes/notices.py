"""お知らせと通知設定の API。"""

from datetime import UTC, datetime

from flask import Blueprint, jsonify
from sqlalchemy import func, or_, select

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import AppSetting, Notice, NoticeRead, User
from ..models.notice import CHANNELS, PRIORITIES
from .helpers import BadRequest, departments_target, error, json_body, parse_datetime, required_text

bp = Blueprint("notices", __name__)

NOTIFICATION_SETTINGS_KEY = "notification_settings"
# 通知設定の初期値（モックと同じ）。メールは今は送らないため、保存だけできる
DEFAULT_NOTIFICATION_SETTINGS = {
    "events": [
        {
            "key": "inquiry_created",
            "label": "新しい問い合わせを受け付けたとき",
            "description": "担当部署の担当者に通知します",
            "inApp": True,
            "email": True,
        },  # noqa: E501
        {
            "key": "inquiry_replied",
            "label": "問い合わせに回答があったとき",
            "description": "問い合わせた利用者に通知します",
            "inApp": True,
            "email": True,
        },  # noqa: E501
        {
            "key": "inquiry_overdue",
            "label": "問い合わせが3営業日以上未対応のとき",
            "description": "担当部署と管理者に通知します",
            "inApp": True,
            "email": False,
        },  # noqa: E501
        {
            "key": "document_indexed",
            "label": "資料の取り込みが完了したとき",
            "description": "アップロードした担当者に通知します",
            "inApp": True,
            "email": False,
        },  # noqa: E501
        {
            "key": "document_failed",
            "label": "資料の取り込みに失敗したとき",
            "description": "アップロードした担当者と管理者に通知します",
            "inApp": True,
            "email": True,
        },  # noqa: E501
        {
            "key": "low_rating",
            "label": "AIの回答に低評価が付いたとき",
            "description": "管理者に通知します（資料改善の参考）",
            "inApp": True,
            "email": False,
        },  # noqa: E501
    ],
    "departmentContacts": [
        {"department": "人事部", "email": "jinji@example.co.jp"},
        {"department": "総務部", "email": "somu@example.co.jp"},
        {"department": "経理部", "email": "keiri@example.co.jp"},
        {"department": "情報システム部", "email": "it-help@example.co.jp"},
    ],
    "weeklyReport": {"enabled": True, "dayOfWeek": "mon", "recipients": "admin@example.co.jp"},
}


@bp.errorhandler(BadRequest)
def _bad_request(e: BadRequest):
    return error(str(e), 400)


def _targets(user: User):
    """利用者が配信先に含まれるお知らせの条件（全員向け、または所属部署向け）。"""
    return or_(
        func.cardinality(Notice.target_departments) == 0,
        Notice.target_departments.contains([user.department]),
    )


@bp.get("/notices")
@login_required
def list_mine():
    """自分あての配信中のお知らせ（既読かどうかを含む）。"""
    user = current_user()
    now = datetime.now(UTC)
    read_ids = set(
        db.session.scalars(select(NoticeRead.notice_id).where(NoticeRead.user_id == user.id))
    )
    notices = db.session.scalars(
        select(Notice)
        .where(
            Notice.is_draft.is_(False),
            or_(Notice.publish_at.is_(None), Notice.publish_at <= now),
            or_(Notice.expire_at.is_(None), Notice.expire_at >= now),
            _targets(user),
        )
        .order_by(Notice.publish_at.desc())
    )
    return jsonify(
        [
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "priority": n.priority,
                "publishAt": n.publish_at.isoformat() if n.publish_at else None,
                "read": n.id in read_ids,
            }
            for n in notices
        ]
    )


@bp.post("/notices/<int:notice_id>/read")
@login_required
def mark_read(notice_id: int):
    user = current_user()
    if db.session.get(Notice, notice_id) is None:
        return error("お知らせが見つかりません", 404)
    exists = db.session.scalar(
        select(NoticeRead).where(NoticeRead.notice_id == notice_id, NoticeRead.user_id == user.id)
    )
    if exists is None:
        db.session.add(NoticeRead(notice_id=notice_id, user_id=user.id))
        db.session.commit()
    return "", 204


def _with_counts(notices: list[Notice]) -> list[dict]:
    """既読数と配信対象の人数をまとめて数えて、API の形にする。"""
    read_counts = dict(
        db.session.execute(
            select(NoticeRead.notice_id, func.count())
            .where(NoticeRead.notice_id.in_([n.id for n in notices]))
            .group_by(NoticeRead.notice_id)
        ).all()
    )
    users_by_department = dict(
        db.session.execute(
            select(User.department, func.count())
            .where(User.status != "suspended")
            .group_by(User.department)
        ).all()
    )
    total = sum(users_by_department.values())
    result = []
    for notice in notices:
        target = (
            sum(users_by_department.get(d, 0) for d in notice.target_departments)
            if notice.target_departments
            else total
        )
        result.append(notice.to_dict(read_counts.get(notice.id, 0), target))
    return result


@bp.get("/admin/notices")
@roles_required("staff", "admin")
def list_all():
    notices = list(db.session.scalars(select(Notice).order_by(Notice.created_at.desc())))
    return jsonify(_with_counts(notices))


@bp.get("/admin/notices/<int:notice_id>")
@roles_required("staff", "admin")
def get(notice_id: int):
    notice = db.session.get(Notice, notice_id)
    if notice is None:
        return error("お知らせが見つかりません", 404)
    return jsonify(_with_counts([notice])[0])


def _apply_input(notice: Notice, data: dict) -> None:
    """NoticeInput（docs/api-spec.md）をお知らせに反映する。"""
    notice.title = required_text(data, "title", "タイトル", 200)
    notice.body = required_text(data, "body", "本文", 10000)
    if data.get("priority", "normal") not in PRIORITIES:
        raise BadRequest("重要度の値が正しくありません")
    notice.priority = data.get("priority", "normal")
    notice.target_departments = departments_target(data.get("target"), "配信先")
    channels = [c for c in data.get("channels") or [] if c in CHANNELS]
    if not channels:
        raise BadRequest("配信方法を 1 つ以上選択してください")
    notice.channels = channels
    notice.is_draft = bool(data.get("isDraft"))
    now = datetime.now(UTC)
    publish_at = parse_datetime(data.get("publishAt"))
    if publish_at is None and not notice.is_draft:
        # 配信日時の指定がなければ今すぐ配信する。配信済みのものを編集したときは元の日時を残す
        already_published = notice.publish_at is not None and notice.publish_at <= now
        publish_at = notice.publish_at if already_published else now
    notice.publish_at = publish_at
    notice.expire_at = parse_datetime(data.get("expireAt"))
    if notice.publish_at and notice.expire_at and notice.expire_at <= notice.publish_at:
        raise BadRequest("掲載の終了日時は、配信日時より後にしてください")


@bp.post("/admin/notices")
@roles_required("staff", "admin")
def create():
    user = current_user()
    notice = Notice(created_by_id=user.id, created_by_name=user.name)
    _apply_input(notice, json_body())
    db.session.add(notice)
    db.session.commit()
    return jsonify(_with_counts([notice])[0]), 201


@bp.put("/admin/notices/<int:notice_id>")
@roles_required("staff", "admin")
def update(notice_id: int):
    notice = db.session.get(Notice, notice_id)
    if notice is None:
        return error("お知らせが見つかりません", 404)
    _apply_input(notice, json_body())
    db.session.commit()
    return jsonify(_with_counts([notice])[0])


@bp.delete("/admin/notices/<int:notice_id>")
@roles_required("staff", "admin")
def delete(notice_id: int):
    notice = db.session.get(Notice, notice_id)
    if notice is None:
        return error("お知らせが見つかりません", 404)
    db.session.delete(notice)
    db.session.commit()
    return "", 204


@bp.get("/admin/notification-settings")
@roles_required("admin")
def get_settings():
    setting = db.session.get(AppSetting, NOTIFICATION_SETTINGS_KEY)
    return jsonify(setting.value if setting else DEFAULT_NOTIFICATION_SETTINGS)


@bp.put("/admin/notification-settings")
@roles_required("admin")
def save_settings():
    """通知設定を保存する。メールは今は送らないため、設定は保存するだけ（ai.md 参照）。"""
    data = json_body()
    shapes = {"events": list, "departmentContacts": list, "weeklyReport": dict}
    if not all(isinstance(data.get(key), shape) for key, shape in shapes.items()):
        raise BadRequest("通知設定の形式が正しくありません")
    value = {k: data[k] for k in ("events", "departmentContacts", "weeklyReport")}
    setting = db.session.get(AppSetting, NOTIFICATION_SETTINGS_KEY)
    if setting is None:
        db.session.add(AppSetting(key=NOTIFICATION_SETTINGS_KEY, value=value))
    else:
        setting.value = value
    db.session.commit()
    return jsonify(value)
