"""Unify hitl_requests into tasks

Revision ID: 20260327T140000h_r003
Revises: 20260327T130000h_r002
Create Date: 2026-03-27 14:00:00.000000
"""
from alembic import op

revision = '20260327T140000h_r003'
down_revision = '20260327T130000h_r002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hitl_requests")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("""
        CREATE TABLE tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project TEXT NOT NULL,
            title TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending', 'in_progress', 'done', 'confirmed', 'cancelled')),
            type VARCHAR(10) DEFAULT 'task'
                CHECK (type IN ('task', 'hitl')),
            workflow_id TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
