"""Initial schema: project, tasks, project_requirement, tasks_xref_project_requirement

Revision ID: r001
Revises:
Create Date: 2026-03-28
"""
from alembic import op

revision = "r001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE project (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL UNIQUE,
            priority    INTEGER NOT NULL DEFAULT 5,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            modified_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE tasks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES project(id),
            title       TEXT NOT NULL,
            priority    INTEGER,
            status      VARCHAR(20) DEFAULT 'pending'
                            CHECK (status IN ('pending', 'in_progress', 'done', 'cancelled')),
            type        VARCHAR(10) DEFAULT 'task'
                            CHECK (type IN ('task', 'hitl')),
            workflow_id TEXT UNIQUE,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            modified_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE project_requirements (
            id           BIGSERIAL PRIMARY KEY,
            project_id   UUID NOT NULL REFERENCES project(id),
            description  TEXT NOT NULL,
            status       VARCHAR(20) DEFAULT 'todo'
                             CHECK (status IN ('todo', 'implementing', 'done')),
            workflow_id  TEXT REFERENCES tasks(workflow_id),
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE tasks_xref_project_requirements (
            task_id                  UUID NOT NULL REFERENCES tasks(id),
            project_requirement_id   BIGINT NOT NULL REFERENCES project_requirements(id),
            PRIMARY KEY (task_id, project_requirement_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks_xref_project_requirements")
    op.execute("DROP TABLE IF EXISTS project_requirements")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TABLE IF EXISTS project")
