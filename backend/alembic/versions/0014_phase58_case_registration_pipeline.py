'''phase 58 case registration pipeline

Revision ID: 0014_phase58_case_registration
Revises: 0013_phase56_development_cases
'''
from alembic import op
import sqlalchemy as sa


revision = '0014_phase58_case_registration'
down_revision = '0013_phase56_development_cases'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'development_cases',
        sa.Column('data_classification', sa.String(50), server_default='UNVERIFIED', nullable=False),
    )
    op.add_column(
        'development_cases',
        sa.Column(
            'provenance',
            sa.JSON(),
            server_default=sa.text(chr(39) + '{}' + chr(39)),
            nullable=False,
        ),
    )
    op.add_column(
        'development_cases',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_column('development_cases', 'updated_at')
    op.drop_column('development_cases', 'provenance')
    op.drop_column('development_cases', 'data_classification')
