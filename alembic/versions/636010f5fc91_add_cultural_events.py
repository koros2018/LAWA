"""add_cultural_events

Revision ID: 636010f5fc91
Revises: 47e932091336
Create Date: 2026-06-01 10:58:38.212613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '636010f5fc91'
down_revision: Union[str, Sequence[str], None] = '47e932091336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加文化活动 & 用户活动表"""
    op.create_table('cultural_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('emoji', sa.String(length=5), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('zone_code', sa.String(length=20), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('requirement_level', sa.Integer(), nullable=True),
    sa.Column('requirement_quest', sa.String(length=40), nullable=True),
    sa.Column('tasks', sa.JSON(), nullable=True),
    sa.Column('rewards', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('user_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('event_id', sa.String(length=36), nullable=False),
    sa.Column('task_index', sa.Integer(), nullable=True),
    sa.Column('task_progress', sa.Integer(), nullable=True),
    sa.Column('completed_tasks', sa.JSON(), nullable=True),
    sa.Column('completed', sa.Boolean(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['cultural_events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('user_events')
    op.drop_table('cultural_events')
