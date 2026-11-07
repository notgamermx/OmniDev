"""Persist conversations shared by every interface."""
from alembic import op
import sqlalchemy as sa
revision = "0007_conversations"
down_revision = "0006_shared_sessions"
branch_labels = depends_on = None

def upgrade():
    op.create_table("conversations", sa.Column("id", sa.String(64), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("messages", sa.Text(), nullable=False), sa.Column("updated_at", sa.String(40), nullable=False))

def downgrade():
    op.drop_table("conversations")
