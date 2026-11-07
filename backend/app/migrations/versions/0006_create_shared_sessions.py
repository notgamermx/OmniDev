"""Create shared sessions tables for collaborative work."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_shared_sessions"
down_revision = "0005_memory_tables"
branch_labels = None
depends_on = None


def upgrade():
    """Create shared session tables."""

    # Shared sessions - sessions that can be shared between users
    op.create_table(
        "shared_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(256), nullable=False, unique=True, index=True),
        sa.Column("owner_user_id", sa.String(256), nullable=False),
        sa.Column("shared_with", sa.JSON(), nullable=False, default=[]),
        sa.Column("permission", sa.String(32), nullable=False, default="read"),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("session_name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("access_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_accessed", sa.String(32), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )

    # Session memberships - tracks who has joined which session
    op.create_table(
        "shared_session_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(256), nullable=False, index=True),
        sa.Column("user_id", sa.String(256), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, default="viewer"),
        sa.Column("joined_at", sa.String(32), nullable=False),
        sa.Column("last_seen", sa.String(32), nullable=True),
        sa.Column("activities", sa.Integer(), nullable=False, default=0),
    )
    op.create_index("uq_session_user", "shared_session_memberships", ["session_id", "user_id"], unique=True)

    # WebSocket sessions - tracking active connections for real-time updates
    op.create_table(
        "websocket_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(256), nullable=False, index=True),
        sa.Column("connection_id", sa.String(256), nullable=False, unique=True),
        sa.Column("user_id", sa.String(256), nullable=False),
        sa.Column("connected_at", sa.String(32), nullable=False),
        sa.Column("last_ping", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("channels", sa.JSON(), nullable=False, default=[]),
    )


def downgrade():
    """Drop shared session tables."""
    op.drop_table("websocket_sessions")
    op.drop_table("shared_session_memberships")
    op.drop_table("shared_sessions")