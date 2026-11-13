"""remove invited status

メールを送らないことにしたため、利用者の「招待中」（invited）をなくす。
招待中の利用者はパスワードがなくログインできないので、「利用停止」（suspended）にする。
管理者が「パスワード再設定」でパスワードを決めて「利用再開」すれば使えるようになる。

Revision ID: 82e081ed0ed8
Revises: c44ed2324f65
Create Date: 2026-11-12 14:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '82e081ed0ed8'
down_revision = 'c44ed2324f65'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET status = 'suspended' WHERE status = 'invited'")


def downgrade():
    # どの利用者が招待中だったかは残っていないため、戻さない
    pass
