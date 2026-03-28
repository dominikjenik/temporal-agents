import uuid
from datetime import datetime, timezone

import aiosqlite
from temporalio import activity

from .hitl_db import _db_path, _init_db


@activity.defn
async def capture_lesson(
    workflow_id: str,
    agent_type: str,
    outcome: str,
    lesson_text: str,
) -> None:
    """Record a learning request as a 'lesson' task in the DB (project='temporal')."""
    activity.heartbeat()

    record_id = uuid.uuid4()
    now = datetime.now(timezone.utc).isoformat()
    title = f"[{outcome.upper()}] {agent_type}: {lesson_text[:120]}"

    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO tasks (id, project, title, priority, status, type, workflow_id, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', 'lesson', ?, ?)",
            (str(record_id), "temporal", title, 5, workflow_id, now),
        )
        await db.commit()
