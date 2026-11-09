"""flask コマンドに追加する管理用コマンド。"""

import os

import click
from flask import Flask
from sqlalchemy import select

from .extensions import db
from .models import User

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
