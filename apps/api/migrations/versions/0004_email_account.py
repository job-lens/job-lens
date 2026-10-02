"""Email verification and atomic credential revocation."""
from alembic import op
import sqlalchemy as sa

revision = '0004_email_account'
down_revision = '0003_identity_limiter'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('users', 'sessions'):
        op.add_column(table, sa.Column('credential_version', sa.Integer(), nullable=False, server_default='1'))
        op.create_check_constraint(f'ck_{table}_credential_version', table, 'credential_version >= 1')
    op.create_table('email_challenges',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('email', sa.String(80), nullable=False),
        sa.Column('purpose', sa.String(16), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.Column('code_hash', sa.String(255)),
        sa.Column('token_hash', sa.String(64), unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True)),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.UniqueConstraint('email', 'purpose'),
        sa.CheckConstraint("purpose IN ('registration','reset')", name='ck_email_challenges_purpose'),
        sa.CheckConstraint('attempts BETWEEN 0 AND 5', name='ck_email_challenges_attempts'),
        sa.CheckConstraint("(purpose = 'registration' AND code_hash IS NOT NULL AND token_hash IS NULL) OR (purpose = 'reset' AND token_hash IS NOT NULL AND code_hash IS NULL)", name='ck_email_challenges_digest'))


def downgrade():
    op.drop_table('email_challenges')
    for table in ('sessions', 'users'):
        op.drop_constraint(f'ck_{table}_credential_version', table, type_='check')
        op.drop_column(table, 'credential_version')
