"""Add conversations table and extend project with repos, env_file.

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
    op.execute("""
        ALTER TABLE project_requirements RENAME TO tickets
    """)
    op.execute("""
        ALTER TABLE tasks_xref_project_requirements RENAME TO tasks_xref_tickets
    """)
    op.execute("""
        ALTER TABLE tasks_xref_tickets 
            RENAME CONSTRAINT tasks_xref_project_requirements_pkey TO tasks_xref_tickets_pkey
    """)
    op.execute("""
        ALTER TABLE tasks_xref_tickets 
            RENAME CONSTRAINT tasks_xref_project_requirements_project_requirement_id_fkey 
            TO tasks_xref_tickets_project_requirement_id_fkey
    """)
    op.execute("""
        ALTER TABLE tasks_xref_tickets 
            RENAME CONSTRAINT tasks_xref_project_requirements_task_id_fkey 
            TO tasks_xref_tickets_task_id_fkey
    """)
    op.execute("""
        ALTER TABLE tickets 
            RENAME CONSTRAINT project_requirements_project_id_fkey 
            TO tickets_project_id_fkey
    """)
    op.execute("""
        ALTER TABLE tickets RENAME COLUMN project_requirement_id TO ticket_id
    """)
    op.execute("""
        ALTER TABLE tickets 
            RENAME CONSTRAINT project_requirements_pkey TO tickets_pkey
    """)
    op.execute("""
        ALTER TABLE tickets 
            RENAME CONSTRAINT project_requirements_workflow_id_fkey 
            TO tickets_workflow_id_fkey
    """)
    op.execute("""
        ALTER TABLE tickets 
            ADD CONSTRAINT tickets_workflow_id_fkey 
            FOREIGN KEY (workflow_id) REFERENCES tasks(workflow_id)
    """)
    op.execute("""
        ALTER TABLE project
            ADD COLUMN repos     JSONB NOT NULL DEFAULT '[]',
            ADD COLUMN env_file  TEXT  NOT NULL DEFAULT ''
    """)
    op.execute("""
        CREATE TABLE conversations (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    TEXT NOT NULL,
            task_id    UUID REFERENCES tasks(id),
            role       VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
            content    TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ON conversations (user_id, created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("ALTER TABLE project DROP COLUMN repos")
    op.execute("ALTER TABLE project DROP COLUMN env_file")
    op.execute("ALTER TABLE tickets RENAME TO project_requirements")
    op.execute(
        "ALTER TABLE tasks_xref_tickets RENAME TO tasks_xref_project_requirements"
    )
