"""add city districts and building layout

Revision ID: f4d0b8c3e2a9
Revises: d2b8e3f6a7c1
Create Date: 2026-08-30 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f4d0b8c3e2a9'
down_revision: Union[str, Sequence[str], None] = 'd2b8e3f6a7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    The catalog rows themselves are not seeded here: the application syncs them
    from app/city_districts.py on first read, so code and table cannot drift.

    `building_family_key` already exists (initial schema created it), so the
    column reuses the type with create_type=False. Without that, this revision
    passes on a fresh database and fails on every existing one.
    """
    op.create_table('city_districts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=32), nullable=False),
    sa.Column('building_family', postgresql.ENUM('sport', 'study', 'work', 'creativity', 'meditation', 'reading', 'custom', name='building_family_key', create_type=False), nullable=True),
    sa.Column('title', sa.String(length=80), nullable=False),
    sa.Column('grid_x', sa.Integer(), nullable=False),
    sa.Column('grid_y', sa.Integer(), nullable=False),
    sa.Column('grid_w', sa.Integer(), nullable=False),
    sa.Column('grid_h', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_city_districts_key'), 'city_districts', ['key'], unique=True)

    op.add_column('city_buildings', sa.Column('district_id', sa.UUID(), nullable=True))
    op.add_column('city_buildings', sa.Column('position_x', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('city_buildings', sa.Column('position_y', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('city_buildings', sa.Column('rotation', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('city_buildings', sa.Column('variant', sa.Integer(), nullable=False, server_default='1'))
    op.create_foreign_key(
        'fk_city_buildings_district_id', 'city_buildings', 'city_districts', ['district_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_city_buildings_district_id', 'city_buildings', type_='foreignkey')
    op.drop_column('city_buildings', 'variant')
    op.drop_column('city_buildings', 'rotation')
    op.drop_column('city_buildings', 'position_y')
    op.drop_column('city_buildings', 'position_x')
    op.drop_column('city_buildings', 'district_id')
    op.drop_index(op.f('ix_city_districts_key'), table_name='city_districts')
    op.drop_table('city_districts')
