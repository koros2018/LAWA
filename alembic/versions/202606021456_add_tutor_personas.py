"""add_tutor_personas

Revision ID: 202606021456
Revises: 636010f5fc91
Create Date: 2026-06-02T14:56:03.947790

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606021456"
down_revision: Union[str, None] = "636010f5fc91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TutorPersona
    op.create_table(
        "tutor_personas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tutor_name", sa.String(50), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False, server_default="en"),
        sa.Column("teaching_style", sa.String(30), nullable=False, server_default="patient_explainer"),
        sa.Column("personality", postgresql.JSON(), nullable=True),
        sa.Column("humor_style", sa.String(30), nullable=True, server_default="light_puns"),
        sa.Column("voice_tone", sa.String(30), nullable=True, server_default="warm_professional"),
        sa.Column("expertise", postgresql.JSON(), nullable=True),
        sa.Column("default_strategies", postgresql.JSON(), nullable=True),
        sa.Column("sessions_conducted", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_messages", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("avg_rating", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("current_difficulty", sa.String(10), nullable=True, server_default="adaptive"),
        sa.Column("tutor_intro", sa.Text(), nullable=True),
        sa.Column("avatar_emoji", sa.String(10), nullable=True, server_default="🦉"),
        sa.Column("is_public", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("rental_coins", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("evolution_history", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_tutor_personas_user_id", "tutor_personas", ["user_id"])

    # TutorConversation
    op.create_table(
        "tutor_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_type", sa.String(30), nullable=True, server_default="general_chat"),
        sa.Column("metadata_json", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tutor_conversations_user_id", "tutor_conversations", ["user_id"])
    op.create_index("ix_tutor_conversations_created_at", "tutor_conversations", ["created_at"])

    # TutorMemoryNote
    op.create_table(
        "tutor_memory_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_recalled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recall_count", sa.Integer(), nullable=True, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tutor_memory_notes_user_id", "tutor_memory_notes", ["user_id"])


def downgrade() -> None:
    op.drop_table("tutor_memory_notes")
    op.drop_table("tutor_conversations")
    op.drop_table("tutor_personas")
