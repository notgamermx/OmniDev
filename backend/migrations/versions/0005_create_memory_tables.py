"""Create memory tables for session, project, and preference storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = "0005_memory_tables"
down_revision = "0004_create_agent_engine"
branch_labels = None
depends_on = None


def upgrade():
    """Create memory tables."""

    # Session memories - transient per-session storage
    op.create_table(
        "session_memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(256), nullable=False, index=True),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("uq_session_key", "session_memories", ["session_id", "key"], unique=True)

    # Project memories - understanding of specific projects
    op.create_table(
        "project_memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False, index=True),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("uq_project_key", "project_memories", ["project_id", "key"], unique=True)

    # Long-term preferences - user configurations across sessions
    op.create_table(
        "long_term_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(256), nullable=False, default="default", index=True),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("scope", sa.String(32), nullable=False, default="global"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("uq_user_category_key", "long_term_preferences", ["user_id", "category", "key"], unique=True)

    # Context retrieval history - for learning retrieval patterns
    op.create_table(
        "context_retrievals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(256), nullable=False, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("similarity", sa.String(32), nullable=True),
        sa.Column("used", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )

    # Project understanding - structured AI understanding of projects
    op.create_table(
        "project_understandings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False, unique=True, index=True),
        sa.Column("understanding", sa.JSON(), nullable=False),
        sa.Column("last_updated", sa.String(32), nullable=False),
        sa.Column("update_reason", sa.String(256), nullable=True),
    )


def downgrade():
    """Drop memory tables."""
    op.drop_table("project_understandings")
    op.drop_table("context_retrievals")
    op.drop_table("long_term_preferences")
    op.drop_table("project_memories")
    op.drop_table("session_memories")