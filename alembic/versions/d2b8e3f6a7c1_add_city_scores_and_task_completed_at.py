"""add city scores and paired task completed_at

Revision ID: d2b8e3f6a7c1
Revises: c1a7f2d4e5b6
Create Date: 2026-08-30 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b8e3f6a7c1'
down_revision: Union[str, Sequence[str], None] = 'c1a7f2d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('city_scores',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('period', sa.Enum('all_time', 'weekly', 'monthly', name='leaderboard_period'), nullable=False),
    sa.Column('period_key', sa.String(length=16), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'period', 'period_key', name='uq_city_score_period')
    )
    op.create_index(op.f('ix_city_scores_company_id'), 'city_scores', ['company_id'], unique=False)
    op.add_column('paired_tasks', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('paired_tasks', 'completed_at')
    op.drop_index(op.f('ix_city_scores_company_id'), table_name='city_scores')
    op.drop_table('city_scores')
    sa.Enum(name='leaderboard_period').drop(op.get_bind(), checkfirst=True)
