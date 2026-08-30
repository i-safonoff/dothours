"""add notifications and user timezone

Revision ID: e3c9f1a2b4d7
Revises: b9ce06665364
Create Date: 2026-08-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3c9f1a2b4d7'
down_revision: Union[str, Sequence[str], None] = 'f4d0b8c3e2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('daily_reminder', 'streak_at_risk', 'paired_task_expired', 'paired_task_completed', 'friend_request', name='notification_kind'), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('body', sa.String(length=500), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.add_column('users', sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'timezone')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    sa.Enum(name='notification_kind').drop(op.get_bind(), checkfirst=True)
