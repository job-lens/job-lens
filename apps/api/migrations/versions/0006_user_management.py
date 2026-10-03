"""Add explicitly provisioned administration and auditable certification review."""
from alembic import op
import sqlalchemy as sa

revision = '0006_user_management'
down_revision = '0005_sop_plan_version'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('management_version', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('administrator_grants',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
    )
    op.create_table('counselor_certifications',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('statement', sa.String(2000), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('reviewer_id', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.CheckConstraint("state IN ('not_submitted','pending','approved','rejected','revoked')", name='state'),
        sa.CheckConstraint('version >= 1', name='version'),
        sa.CheckConstraint('reviewer_id IS NULL OR reviewer_id != user_id', name='no_self_review'),
    )
    op.create_table('management_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.Column('target_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('trace_id', sa.String(128), nullable=False),
    )


def downgrade():
    op.drop_table('management_events')
    op.drop_table('counselor_certifications')
    op.drop_table('administrator_grants')
    op.drop_column('users', 'management_version')
