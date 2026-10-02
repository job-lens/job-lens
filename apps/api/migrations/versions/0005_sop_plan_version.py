"""Expose a real optimistic version for SOP plan projections."""
from alembic import op
import sqlalchemy as sa

revision = '0005_sop_plan_version'
down_revision = '0004_email_account'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sop_plans', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_check_constraint('ck_sop_plans_version', 'sop_plans', 'version >= 1')


def downgrade():
    op.drop_constraint('ck_sop_plans_version', 'sop_plans', type_='check')
    op.drop_column('sop_plans', 'version')
