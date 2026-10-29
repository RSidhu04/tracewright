"""Immutable run snapshots and baseline versions."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tw_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False),
        sa.Column('suite_hash', sa.String(64), nullable=False),
        sa.Column('payload', sa.Text, nullable=False))
    op.create_index('ix_tw_runs_suite_hash', 'tw_runs', ['suite_hash'])
    op.create_table('tw_baselines',
        sa.Column('name', sa.String(80), primary_key=True),
        sa.Column('version', sa.Integer, primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('tw_runs.id'), nullable=False),
        sa.Column('created_at', sa.String(40), nullable=False),
        sa.Column('note', sa.Text, nullable=False))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead.')
