from alembic import op

revision = 'r001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            priority INTEGER DEFAULT 5,
            repos TEXT DEFAULT '[]',
            env_file TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            modified_at TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            parent_id TEXT REFERENCES tasks(id),
            project TEXT NOT NULL REFERENCES projects(id),
            title TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'TODO' CHECK (status IN ('TODO', 'BLOCKED', 'DONE')),
            workflow_id TEXT,
            created_at TEXT NOT NULL,
            modified_at TEXT NOT NULL,
            conversations TEXT NOT NULL DEFAULT '[]'
        )
    """)

    op.execute("""
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            task_id TEXT,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_user_created 
        ON conversations (user_id, created_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS conversations")