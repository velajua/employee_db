"""first revision

Revision ID: abcdef123456
Revises: None
Create Date: 2024-09-10 14:20:00.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'abcdef123456'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('department', sa.String(50), nullable=False),
    )
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('job', sa.String(50), nullable=False),
    )
    op.create_table(
        'hired_employees',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('datetime', sa.DateTime, nullable=False),
        sa.Column('department_id', sa.Integer, nullable=False),
        sa.Column('job_id', sa.Integer, nullable=False),
    )


def downgrade():
    op.drop_table('hired_employees')
    op.drop_table('jobs')
    op.drop_table('departments')
