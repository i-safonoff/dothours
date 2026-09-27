"""add email notifications enabled to users

Revision ID: 6886c451eb1e
Revises: e3c9f1a2b4d7
Create Date: 2026-09-30 17:55:20.162713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6886c451eb1e'
down_revision: Union[str, Sequence[str], None] = 'e3c9f1a2b4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default, not just the model's Python-side default: autogenerate
    # left this off, which is fine against an empty table and breaks the
    # NOT NULL constraint against a real one with existing rows -- the same
    # thing e3c9f1a2b4d7 already got right for `timezone`.
    op.add_column(
        'users',
        sa.Column('email_notifications_enabled', sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'email_notifications_enabled')
