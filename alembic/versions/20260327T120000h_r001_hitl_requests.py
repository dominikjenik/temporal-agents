"""hitl_requests table

Revision ID: 20260327T120000h_r001
Revises:
Create Date: 2026-03-27 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260327T120000h_r001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE hitl_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id TEXT NOT NULL,
            description TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hitl_requests")
