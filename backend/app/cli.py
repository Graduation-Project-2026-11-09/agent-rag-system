"""flask コマンドに追加する管理用コマンド。"""

import os

import click
from flask import Flask
from sqlalchemy import select

from .extensions import db
from .models import User
from .models.user import ROLES

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
