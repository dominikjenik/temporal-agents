"""Rename project_requirements to tickets.

Revision ID: r003
Revises: r001
Create Date: 2026-04-03
"""

from alembic import op

revision = "r003"
down_revision = "r001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE project_requirements RENAME TO tickets")


def downgrade() -> None:
    op.execute("ALTER TABLE tickets RENAME TO project_requirements")
