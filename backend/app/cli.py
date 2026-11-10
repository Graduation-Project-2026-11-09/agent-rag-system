"""flask コマンドに追加する管理用コマンド。"""

import json
import os
from datetime import date
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import select

from .extensions import db
from .ingestion.registration import RegistrationError, register_document
from .models import Document, User
from .models.user import ROLES

# ダミー資料（架空の会社の規程・マニュアル）。seed/build_documents.py で各形式のファイルを作る
SEED_DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "seed" / "documents"

# モックアップ（frontend/src/mocks/db.js）と同じダミーの利用者。開発・stg の動作確認に使う
SEED_USERS = [
    ("E10234", "山田 花子", "yamada@example.co.jp", "営業部", "user", None),
    ("E00451", "佐藤 美咲", "sato@example.co.jp", "人事部", "staff", "人事部"),
    ("E00502", "鈴木 一郎", "suzuki@example.co.jp", "総務部", "staff", "総務部"),
    ("E00611", "高橋 健太", "takahashi@example.co.jp", "経理部", "staff", "経理部"),
    ("E00012", "管理 太郎", "admin@example.co.jp", "情報システム部", "admin", "情報システム部"),
]


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-users")
    def seed_users() -> None:
        """ダミーの利用者を登録する（既に登録済みの利用者は変更しない）。

        パスワードは環境変数 SEED_USER_PASSWORD（stg では SSM Parameter Store）で指定する。
        """
        password = os.environ.get("SEED_USER_PASSWORD")
        if not password:
            raise click.ClickException("SEED_USER_PASSWORD が設定されていません")

        created = 0
        for employee_id, name, email, department, role, handles in SEED_USERS:
            if db.session.scalar(select(User).where(User.email == email)):
                continue
            user = User(
                employee_id=employee_id,
                name=name,
                email=email,
                department=department,
                role=role,
                handles_department=handles,
                status="active",
            )
            user.set_password(password)
            db.session.add(user)
            created += 1
        db.session.commit()
        click.echo(f"seed-users: {created} 件登録しました")

    @app.cli.command("create-user")
    @click.option("--email", required=True, help="ログイン ID になるメールアドレス")
    @click.option("--name", required=True, help="氏名")
    @click.option("--employee-id", required=True, help="社員番号")
    @click.option("--department", required=True, help="所属部署")
    @click.option("--role", type=click.Choice(ROLES), default="user", show_default=True)
    @click.option("--handles-department", default=None, help="部署担当者・管理者が対応する部署")
    @click.option(
        "--password-env",
        default="SEED_USER_PASSWORD",
        show_default=True,
        help="パスワードを読み取る環境変数名（コマンド履歴に残さないため、値は直接渡さない）",
    )
    def create_user(
        email: str,
        name: str,
        employee_id: str,
        department: str,
        role: str,
        handles_department: str | None,
        password_env: str,
    ) -> None:
        """利用者を1人登録する。登録済みのメールアドレスなら何もしない。

        アカウント管理画面ができるまで、メンバーのアカウント作成に使う。
        個人のメールアドレスを公開リポジトリに残さないよう、seed-users には含めない。
        """
        password = os.environ.get(password_env)
        if not password:
            raise click.ClickException(f"{password_env} が設定されていません")

        email = email.strip().lower()
        if db.session.scalar(select(User).where(User.email == email)):
            click.echo(f"create-user: {email} は登録済みのため変更しません")
            return
        if db.session.scalar(select(User).where(User.employee_id == employee_id)):
            raise click.ClickException(f"社員番号 {employee_id} は登録済みです")

        user = User(
            employee_id=employee_id,
            name=name,
            email=email,
            department=department,
            role=role,
            handles_department=handles_department,
            status="active",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"create-user: {email}（{role}）を登録しました")

    @app.cli.command("import-document")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option("--title", default=None, help="資料名（省略時はファイル名）")
    @click.option("--department", required=True, help="資料を管理する部署")
    @click.option("--category", default=None, help="資料の分類")
    @click.option(
        "--visible-department",
        "visible_departments",
        multiple=True,
        help="閲覧できる部署（複数指定可）。省略すると全員が閲覧できる",
    )
    @click.option("--tag", "tags", multiple=True, help="タグ（複数指定可）")
    def import_document(
        path: Path,
        title: str | None,
        department: str,
        category: str | None,
        visible_departments: tuple[str, ...],
        tags: tuple[str, ...],
    ) -> None:
        """資料ファイルを登録し、取り込み待ちにする（取り込みは worker が行う）。

        資料管理画面ができるまで、ダミー資料の登録と動作確認に使う。
        本物の社内資料は登録しないこと（OpenAI API に送られるため）。
        """
        try:
            document = register_document(
                path.name,
                path.read_bytes(),
                title=title or path.stem,
                department=department,
                category=category,
                visibility_type="departments" if visible_departments else "all",
                visible_departments=visible_departments,
                tags=tags,
            )
        except RegistrationError as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"import-document: 「{document.title}」を登録しました（id={document.id}）")

    @app.cli.command("seed-documents")
    @click.option(
        "--dir",
        "seed_dir",
        type=click.Path(exists=True, file_okay=False, path_type=Path),
        default=SEED_DOCUMENTS_DIR,
        show_default=True,
        help="manifest.json と files/ があるフォルダ",
    )
    def seed_documents(seed_dir: Path) -> None:
        """ダミー資料をまとめて登録し、取り込み待ちにする（取り込みは worker が行う）。

        同じ資料名の資料が登録済みなら何もしない。登録者は、資料を管理する部署の担当者にする。
        """
        manifest = json.loads((seed_dir / "manifest.json").read_text(encoding="utf-8"))
        created = 0
        for entry in manifest["documents"]:
            if db.session.scalar(select(Document).where(Document.title == entry["title"])):
                continue
            files = list((seed_dir / "files").glob(f"{entry['slug']}.*"))
            if len(files) != 1:
                raise click.ClickException(
                    f"{entry['slug']} のファイルが見つかりません（seed/build_documents.py で作成）"
                )
            uploader = db.session.scalar(
                select(User).where(
                    User.role.in_(("staff", "admin")),
                    User.handles_department == entry["department"],
                )
            )
            visible_departments = entry.get("visibleDepartments") or []
            try:
                register_document(
                    files[0].name,
                    files[0].read_bytes(),
                    title=entry["title"],
                    department=entry["department"],
                    category=entry.get("category"),
                    visibility_type="departments" if visible_departments else "all",
                    visible_departments=visible_departments,
                    tags=entry.get("tags", []),
                    effective_date=(
                        date.fromisoformat(entry["effectiveDate"])
                        if entry.get("effectiveDate")
                        else None
                    ),
                    uploaded_by=uploader,
                )
            except RegistrationError as e:
                raise click.ClickException(f"{entry['slug']}: {e}") from e
            created += 1
        click.echo(f"seed-documents: {created} 件登録しました（取り込みは worker が行います）")
