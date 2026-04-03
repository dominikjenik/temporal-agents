import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from pydantic import BaseModel
from temporalio import activity

DB_URL: str = os.environ.get("HITL_DB_URL", "sqlite:////tmp/hitl.db")


def _db_path() -> str:
    url = DB_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("sqlite://"):
        return url[len("sqlite://") :]
    return url


async def _init_db(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            task_id TEXT,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_user_created 
        ON conversations (user_id, created_at)
    """)
    await db.commit()


class Conversation(BaseModel):
    id: str
    user_id: str
    task_id: Optional[str] = None
    role: str
    content: str
    created_at: str


async def store_message(
    user_id: str,
    role: str,
    content: str,
    task_id: Optional[str] = None,
) -> Conversation:
    """Store a single message in the conversation history."""
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO conversations (id, user_id, task_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record_id, user_id, task_id, role, content, now),
        )
        await db.commit()
    return Conversation(
        id=record_id,
        user_id=user_id,
        task_id=task_id,
        role=role,
        content=content,
        created_at=now,
    )


async def get_conversation_history(
    user_id: str,
    limit: int = 50,
    task_id: Optional[str] = None,
) -> list[Conversation]:
    """Get conversation history for a user, optionally filtered by task_id."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row

        if task_id:
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE user_id = ? AND task_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, task_id, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
        rows = await cursor.fetchall()

    # Reverse to get chronological order
    messages = [
        Conversation(
            id=row["id"],
            user_id=row["user_id"],
            task_id=row["task_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return list(reversed(messages))


async def get_user_conversations(user_id: str) -> list[dict]:
    """Get all conversations for a user, grouped by task_id."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT task_id, COUNT(*) as message_count, MIN(created_at) as first_message, "
            "MAX(created_at) as last_message FROM conversations WHERE user_id = ? "
            "GROUP BY task_id ORDER BY last_message DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()

    return [
        {
            "task_id": row["task_id"],
            "message_count": row["message_count"],
            "first_message": row["first_message"],
            "last_message": row["last_message"],
        }
        for row in rows
    ]


@activity.defn
async def add_user_message(
    user_id: str, content: str, task_id: Optional[str] = None
) -> Conversation:
    """Activity wrapper for storing user message."""
    return await store_message(user_id, "user", content, task_id)


@activity.defn
async def add_assistant_message(
    user_id: str, content: str, task_id: Optional[str] = None
) -> Conversation:
    """Activity wrapper for storing assistant message."""
    return await store_message(user_id, "assistant", content, task_id)


@activity.defn
async def get_conversation(
    user_id: str, limit: int = 50, task_id: Optional[str] = None
) -> list[dict]:
    """Activity wrapper for getting conversation history as list of dicts."""
    messages = await get_conversation_history(user_id, limit, task_id)
    return [{"role": m.role, "content": m.content} for m in messages]
