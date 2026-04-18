import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
import json

import psycopg2
from pydantic import BaseModel
from temporalio import activity

DB_URL: str = os.environ.get("HITL_DB_URL", "postgresql://temporal:temporal@localhost:5432/temporal")

WHITELIST_TABLES = {"tasks", "projects"}


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


class Task(BaseModel):
    id: str
    parent_id: Optional[str] = None
    project: str
    title: str
    priority: int = 5
    status: str = "TODO"
    workflow_id: Optional[str] = None
    created_at: str
    modified_at: str
    conversations: str = "[]"


class DBQuery(BaseModel):
    table: str
    filter: dict = {}
    order: str = ""
    limit: int = 100


@activity.defn
async def store_task(
    project: str,
    title: str,
    priority: int = 5,
    workflow_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Task:
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conversations = "[]"

    

    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO tasks (id, parent_id, project, title, priority, status, workflow_id, created_at, modified_at, conversations)
                   VALUES (%s, %s, %s, %s, %s, 'TODO', %s, %s, %s, %s)""",
                (task_id, parent_id, project, title, priority, workflow_id, now, now, conversations),
            )
        conn.commit()

    return Task(
        id=task_id,
        parent_id=parent_id,
        project=project,
        title=title,
        priority=priority,
        status="TODO",
        workflow_id=workflow_id,
        created_at=now,
        modified_at=now,
        conversations=conversations,
    )


async def _fetch_tasks(status: Optional[str] = None) -> List[Task]:
    

    with _pg_connect() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT id, parent_id, project, title, priority, status, workflow_id, created_at, modified_at, conversations "
                    "FROM tasks WHERE status = %s ORDER BY priority ASC, project ASC",
                    (status,),
                )
            else:
                cur.execute(
                    "SELECT id, parent_id, project, title, priority, status, workflow_id, created_at, modified_at, conversations "
                    "FROM tasks ORDER BY priority ASC, project ASC"
                )
            rows = cur.fetchall()

    return [
        Task(
            id=row[0],
            parent_id=row[1],
            project=row[2],
            title=row[3],
            priority=row[4],
            status=row[5],
            workflow_id=row[6],
            created_at=row[7],
            modified_at=row[8],
            conversations=row[9],
        )
        for row in rows
    ]


@activity.defn
async def update_task_status(workflow_id: str, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET status = %s, modified_at = %s WHERE workflow_id = %s",
                (status, now, workflow_id),
            )
        conn.commit()


@activity.defn
async def list_tasks(status: str = "TODO") -> List[Task]:
    return await _fetch_tasks(status)


@activity.defn
async def create_task(
    project: str,
    title: str,
    priority: int = 5,
    workflow_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Task:
    return await store_task(project, title, priority, workflow_id, parent_id)


@activity.defn
async def complete_task(workflow_id: str) -> None:
    return await update_task_status(workflow_id, "DONE")


@activity.defn
async def add_conversation(task_id: str, role: str, content: str) -> Task:
    now = datetime.now(timezone.utc).isoformat()

    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT conversations FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")

            convs = json.loads(row[0])
            convs.append({"role": role, "content": content, "created_at": now})
            convs_json = json.dumps(convs)

            cur.execute(
                "UPDATE tasks SET conversations = %s, modified_at = %s WHERE id = %s",
                (convs_json, now, task_id),
            )
        conn.commit()

    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, parent_id, project, title, priority, status, workflow_id, created_at, modified_at, conversations "
                "FROM tasks WHERE id = %s",
                (task_id,),
            )
            row = cur.fetchone()

    return Task(
        id=row[0],
        parent_id=row[1],
        project=row[2],
        title=row[3],
        priority=row[4],
        status=row[5],
        workflow_id=row[6],
        created_at=row[7],
        modified_at=row[8],
        conversations=row[9],
    )


@activity.defn
async def execute_db_query(query: DBQuery) -> list[dict]:
    if query.table not in WHITELIST_TABLES:
        raise ValueError(f"Table '{query.table}' is not allowed. Allowed: {WHITELIST_TABLES}")

    with _pg_connect() as conn:
        with conn.cursor() as cur:
            sql = f"SELECT * FROM {query.table}"
            params = []

            if query.filter:
                conditions = [f"{k} = %s" for k in query.filter.keys()]
                sql += " WHERE " + " AND ".join(conditions)
                params.extend(query.filter.values())

            if query.order:
                sql += f" ORDER BY {query.order}"

            sql += f" LIMIT {query.limit}"

            cur.execute(sql, params)
            rows = cur.fetchall()

            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row)) for row in rows]