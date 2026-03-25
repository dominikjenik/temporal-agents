# temporal-agents — Project Structure

## Root
/home/djenik/temporal-agents/

## Tech stack
- Python 3.12, uv
- temporalio Python SDK
- pydantic v2
- pytest + pytest-asyncio (asyncio_mode=auto)

## Top-level files
- `pyproject.toml`       — project metadata and dependencies
- `docker-compose.yml`   — Temporal server dev environment
- `main.py`              — entry point (worker bootstrap)

## Source tree — src/temporal_agents/
```
src/temporal_agents/
├── __init__.py
├── activities/
│   ├── __init__.py        — public exports for the activities package
│   ├── base.py            — ClaudeActivityInput, ClaudeActivityOutput, run_claude_activity
│   ├── agents.py          — developer_activity, tester_activity, developer_zbornik_activity, devops_zbornik_activity
│   └── options.py         — ActivityOptions dataclass + DEVELOPER/TESTER/DEVELOPER_ZBORNIK/DEVOPS_ZBORNIK_OPTIONS
├── signals/
│   └── __init__.py
├── workers/
│   ├── __init__.py          — public exports: ACTIVITIES, WORKFLOWS
│   └── worker.py            — WORKFLOWS = [FeatureWorkflow, ProjectWorkflow], ACTIVITIES list
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
    ├── test_activities.py   — unit tests for activities layer (8 tests)
    └── test_workflows.py    — unit tests for FeatureWorkflow and ProjectWorkflow (7 tests)
```

## Key design decisions
- `run_claude_activity` runs `claude --dangerously-skip-permissions -p <agent_name> "<task>"` as asyncio subprocess
- Heartbeat loop runs as asyncio background task (every 30 s) parallel to `process.communicate()`
- `ActivityOptions` is a dataclass (not TypedDict/dict) so tests can access fields via dot-syntax
- Package installed as editable (`uv pip install -e .`) for test discovery
