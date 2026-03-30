"""Seed: project + project_requirement from PROJECT_REQUIREMENTS.md

Revision ID: r002
Revises: r001
Create Date: 2026-03-28
"""
from alembic import op

revision = "r002"
down_revision = "r001"
branch_labels = None
depends_on = None

TEMPORAL_REQUIREMENTS = [
    "Manager extracts intent from user request; project_status intent returns task list sorted by project priority.",
    "Intent 'implementing' stores project_requirement(status=implementing) and routes to ProjectManagerWorkflow → FeatureWorkflow → developer agent → HITL for approval (confirm/comment signals). Intent 'todo' stores project_requirement(status=todo) only — no workflow launched. UI: task list with 1s polling, detail panel with OK / Comment buttons.",
    "Format check and learning loop: unexpected response format triggers capture_lesson activity which writes lesson row to DB (project=temporal, type=lesson). Agent model defined in frontmatter. retry_policy maximum_attempts=1 for all activities.",
    "End-to-end pipeline: input → Manager resolves new_feature intent → launches ProjectManagerWorkflow as child (ABANDON) → HITL task written to DB → workflow waits for confirm signal (status waiting_hitl).",
    "UI fixes: TaskDetail without workflow_id shows 'Posudenie nedostupne.' instead of infinite loader. Modal title not hidden behind fixed NavBar (backdrop items-start pt-20, modal max-h calc).",
    "UI workflow log: ProjectManagerWorkflow accumulates log entries during run and exposes them via get_log query. API /hitl/{workflow_id}/state returns log array. UI shows compact terminal-style log; loader shows only when log is still empty.",
    "Intent 'chat': user wants to converse without a concrete implementation request — no project required, no requirement stored. IntentResolver resolves to chat; manager returns conversational LLM response. May naturally lead to a new requirement.",
]


def upgrade() -> None:
    op.execute("""
        INSERT INTO project (name, priority) VALUES
            ('temporal', 1),
            ('zbornik', 3),
            ('ginidocs', 3)
    """)

    for description in TEMPORAL_REQUIREMENTS:
        desc_escaped = description.replace("'", "''")
        op.execute(f"""
            INSERT INTO project_requirement (project_id, description)
            SELECT id, '{desc_escaped}'
            FROM project WHERE name = 'temporal'
        """)


def downgrade() -> None:
    op.execute("DELETE FROM project_requirement")
    op.execute("DELETE FROM project")
