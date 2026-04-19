import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List

import psycopg2
from pydantic import BaseModel
from temporalio import activity

DB_URL: str = os.environ.get("HITL_DB_URL", "postgresql://temporal:temporal@localhost:5432/temporal")


def _parse_pg_url(url: str) -> dict:
    url = url.replace("postgresql://", "").replace("postgres://", "")
    if "@" in url:
        auth, rest = url.split("@")
        user, passwd = auth.split(":")
    else:
        user, passwd = "temporal", "temporal"
    if "/" in rest:
        host_port, db = rest.split("/")
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host, port = host_port, 5432
    else:
        host, port, db = rest, 5432, "temporal"
    return {"host": host, "port": port, "database": db, "user": user, "password": passwd}


def _pg_connect():
    return psycopg2.connect(**_parse_pg_url(DB_URL))


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
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, user_id, task_id, role, content, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (record_id, user_id, task_id, role, content, now),
            )
            conn.commit()
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
    
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            if task_id:
                cur.execute(
                    "SELECT id, user_id, task_id, role, content, created_at "
                    "FROM conversations WHERE user_id = %s AND task_id = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (user_id, task_id, limit),
                )
            else:
                cur.execute(
                    "SELECT id, user_id, task_id, role, content, created_at "
                    "FROM conversations WHERE user_id = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
            rows = cur.fetchall()

    messages = [
        Conversation(
            id=row[0],
            user_id=row[1],
            task_id=row[2],
            role=row[3],
            content=row[4],
            created_at=row[5],
        )
        for row in rows
    ]
    return list(reversed(messages))


async def get_user_conversations(user_id: str) -> list[dict]:
    
    with _pg_connect() as cur:
        cur.execute(
            "SELECT task_id, COUNT(*) as message_count, MIN(created_at) as first_message, "
            "MAX(created_at) as last_message FROM conversations WHERE user_id = %s "
            "GROUP BY task_id ORDER BY last_message DESC",
            (user_id,),
        )
        rows = cur.fetchall()

    return [
        {
            "task_id": row[0],
            "message_count": row[1],
            "first_message": row[2],
            "last_message": row[3],
        }
        for row in rows
    ]


@activity.defn
async def add_user_message(
    user_id: str, content: str, task_id: Optional[str] = None
) -> Conversation:
    return await store_message(user_id, "user", content, task_id)


@activity.defn
async def add_assistant_message(
    user_id: str, content: str, task_id: Optional[str] = None
) -> Conversation:
    return await store_message(user_id, "assistant", content, task_id)


@activity.defn
async def get_conversation(
    user_id: str, limit: int = 50, task_id: Optional[str] = None
) -> list[dict]:
    messages = await get_conversation_history(user_id, limit, task_id)
    return [{"role": m.role, "content": m.content} for m in messages]