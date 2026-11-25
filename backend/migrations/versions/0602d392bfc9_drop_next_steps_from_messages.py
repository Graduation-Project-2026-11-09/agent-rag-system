"""drop next_steps from messages

回答の「次に行う手続き」を表示しないことにしたため、保存していた列をなくす。
AI に作らせると出力のトークン（＝費用）が増えるので、生成もやめている。

Revision ID: 0602d392bfc9
Revises: c44ed2324f65
Create Date: 2026-11-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0602d392bfc9'
down_revision = 'c44ed2324f65'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('messages', 'next_steps')


def downgrade():
    # 消した値は戻らない（列だけ作り直す）
    op.add_column(
        'messages',
        sa.Column('next_steps', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
