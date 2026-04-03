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
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'todo',
            created_at TEXT NOT NULL
        )
    """)
    await db.commit()


class Ticket(BaseModel):
    id: str
    project: str
    description: str
    status: str = "todo"
    created_at: str


async def store_ticket(project: str, description: str = "") -> Ticket:
    """Save a new ticket with status=todo."""
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO tickets (id, project, description, status, created_at) "
            "VALUES (?, ?, ?, 'todo', ?)",
            (ticket_id, project, description, now),
        )
        await db.commit()
    return Ticket(
        id=ticket_id,
        project=project,
        description=description,
        status="todo",
        created_at=now,
    )


async def _fetch_tickets(status: Optional[str] = None) -> list[Ticket]:
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                "SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cursor = await db.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    return [
        Ticket(
            id=row["id"],
            project=row["project"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@activity.defn
async def list_tickets(status: str = "todo") -> list[Ticket]:
    return await _fetch_tickets(status)


@activity.defn
async def create_ticket(project: str, description: str = "") -> Ticket:
    """Activity wrapper for store_ticket."""
    return await store_ticket(project, description)
