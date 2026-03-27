"""tasks table

Revision ID: 20260327T130000h_r002
Revises: 20260327T120000h_r001
Create Date: 2026-03-27 13:00:00.000000
"""
from alembic import op

revision = '20260327T130000h_r002'
down_revision = '20260327T120000h_r001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project TEXT NOT NULL,
            title TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
