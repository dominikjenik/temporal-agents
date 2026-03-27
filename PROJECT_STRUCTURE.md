# temporal-agents — Project Structure

## Root
/home/djenik/temporal-agents/

## Tech stack
- Python 3.12, uv
- temporalio Python SDK
- pydantic v2
- pytest + pytest-asyncio (asyncio_mode=auto)

## Top-level files
- `pyproject.toml`       — project metadata and dependencies (includes aiosqlite, click)
- `docker-compose.yml`   — Temporal server dev environment
- `main.py`              — CLI entry point (Click group: hitl command)

## Top-level directories
- `alembic/`
  - `db/`                       — raw SQL migration files (PostgreSQL)
  - `versions/`                 — Alembic Python migration stubs
- `lessons/`               — self-improvement staging area (REQ-015)
  - `pending.md`           — lessons appended by capture_lesson activity, awaiting manual review
  - `README.md`            — explains the self-improvement loop and promotion flow

## Source tree — src/temporal_agents/
```
src/temporal_agents/
├── __init__.py
├── activities/
│   ├── __init__.py        — public exports for the activities package
│   ├── base.py            — ClaudeActivityInput, ClaudeActivityOutput, run_claude_activity
│   ├── agents.py          — developer_activity, tester_activity, developer_zbornik_activity, devops_zbornik_activity
│   ├── hitl_db.py         — store_hitl_request, list_hitl_requests, execute_db_query (PHASE6); HitlRequest, DBQuery models; DB_URL patchable
│   ├── lesson.py          — capture_lesson activity (PHASE5-001, REQ-015)
│   └── options.py         — ActivityOptions dataclass + DEVELOPER/TESTER/DEVELOPER_ZBORNIK/DEVOPS_ZBORNIK/CAPTURE_LESSON/STORE_HITL/LIST_HITL/EXECUTE_DB_QUERY_OPTIONS
├── signals/
│   └── __init__.py
├── workers/
│   ├── __init__.py          — public exports: ACTIVITIES, WORKFLOWS
│   └── worker.py            — WORKFLOWS list, ACTIVITIES list, main() with Client.connect + Worker(task_queue="temporal-agents", max_concurrent_activities=5)
└── workflows/
    ├── __init__.py          — public exports: FeatureInput, FeatureWorkflow, make_feature_workflow_id, ProjectInput, ProjectWorkflow
    ├── feature_workflow.py  — FeatureInput dataclass, FeatureWorkflow (ginidocs: dev+tester, zbornik: dev_zbornik)
    └── project_workflow.py  — ProjectInput dataclass, ProjectWorkflow (ginidocs: parallel, zbornik: sequential), make_feature_workflow_id
```

## Test tree — tests/
```
tests/
├── __init__.py
├── integration/
│   └── __init__.py
└── unit/
    ├── __init__.py
    ├── test_activities.py      — unit tests for activities layer (8 tests)
    ├── test_hitl_db.py         — unit tests for hitl_db activities and options (11 tests, PHASE6)
    ├── test_lesson_activity.py — unit tests for capture_lesson activity (PHASE5-001)
    └── test_workflows.py       — unit tests for FeatureWorkflow and ProjectWorkflow (7 tests)
```

## Key design decisions
- `run_claude_activity` runs `claude --dangerously-skip-permissions -p <agent_name> "<task>"` as asyncio subprocess
- Heartbeat loop runs as asyncio background task (every 30 s) parallel to `process.communicate()`
- `ActivityOptions` is a dataclass with optional `schedule_to_close_timeout` and `start_to_close_timeout` — HITL options use `start_to_close_timeout`, older options use `schedule_to_close_timeout`
- `DB_URL` in hitl_db.py is a module-level string constant — patchable via `unittest.mock.patch` in tests (aiosqlite SQLite backend for tests, PostgreSQL in production)
- Package installed as editable (`uv pip install -e .`) for test discovery
