"""create document tables

Revision ID: d79adad5597a
Revises: cb9975508bd8
Create Date: 2026-11-10 10:00:00.000000

"""
from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd79adad5597a'
down_revision = 'cb9975508bd8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('department', sa.String(length=100), nullable=False),
    sa.Column('visibility_type', sa.String(length=16), nullable=False),
    sa.Column('visible_departments', postgresql.ARRAY(sa.String(length=100)), nullable=False),
    sa.Column('tags', postgresql.ARRAY(sa.String(length=50)), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('processing_stage', sa.String(length=16), nullable=True),
    sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('processing', 'indexed', 'error')", name='ck_documents_status'),
    sa.CheckConstraint("visibility_type IN ('all', 'departments')", name='ck_documents_visibility_type'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_status'), ['status'], unique=False)

    op.create_table('document_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=16), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('pages', sa.Integer(), nullable=True),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=True),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'version')
    )

    op.create_table('document_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('document_version_id', sa.Integer(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.HALFVEC(dim=3072), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_chunks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_chunks_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_chunks_document_version_id'), ['document_version_id'], unique=False)
        # 3072 次元は vector 型の HNSW 索引の上限（2000）を超えるため、halfvec 型で索引を作る
        batch_op.create_index('ix_document_chunks_embedding', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'halfvec_cosine_ops'})


def downgrade():
    with op.batch_alter_table('document_chunks', schema=None) as batch_op:
        batch_op.drop_index('ix_document_chunks_embedding', postgresql_using='hnsw', postgresql_ops={'embedding': 'halfvec_cosine_ops'})
        batch_op.drop_index(batch_op.f('ix_document_chunks_document_version_id'))
        batch_op.drop_index(batch_op.f('ix_document_chunks_document_id'))

    op.drop_table('document_chunks')
    op.drop_table('document_versions')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_status'))

    op.drop_table('documents')
