"""Persist small authentication budgets without Redis."""
from alembic import op
import sqlalchemy as sa

revision = "0003_identity_limiter"
down_revision = "0002_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_limits",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_auth_limits_attempts"))


def downgrade():
    op.drop_table("auth_limits")
