"""add companies, memberships and invites

Revision ID: c1a7f2d4e5b6
Revises: b9ce06665364
Create Date: 2026-08-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a7f2d4e5b6'
down_revision: Union[str, Sequence[str], None] = 'b9ce06665364'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('companies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('avatar_color', sa.String(length=7), nullable=False),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_companies_slug'), 'companies', ['slug'], unique=True)
    op.create_table('company_memberships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('owner', 'admin', 'member', name='company_role'), nullable=False),
    sa.Column('contribution_minutes_total', sa.Integer(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'user_id', name='uq_company_membership')
    )
    op.create_index(op.f('ix_company_memberships_user_id'), 'company_memberships', ['user_id'], unique=False)
    op.create_table('company_invites',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('max_uses', sa.Integer(), nullable=False),
    sa.Column('uses_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_invites_code'), 'company_invites', ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_company_invites_code'), table_name='company_invites')
    op.drop_table('company_invites')
    op.drop_index(op.f('ix_company_memberships_user_id'), table_name='company_memberships')
    op.drop_table('company_memberships')
    op.drop_index(op.f('ix_companies_slug'), table_name='companies')
    op.drop_table('companies')
    sa.Enum(name='company_role').drop(op.get_bind(), checkfirst=True)
