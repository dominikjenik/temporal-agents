import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
import json

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


class Repo(BaseModel):
    title: str
    url: str


class Project(BaseModel):
    id: str
    name: str
    priority: int = 5
    repos: List[Repo] = []
    env_file: str = ""
    created_at: str
    modified_at: str


async def get_project(name: str) -> Optional[Project]:
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (id, name, priority, repos, env_file, created_at, modified_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (record_id, name, priority, repos_json, env_file, now, now),
            )
        conn.commit()

    return Project(
        id=record_id,
        name=name,
        priority=priority,
        repos=[Repo(**r) if isinstance(r, dict) else r for r in (repos or [])],
        env_file=env_file,
        created_at=now,
        modified_at=now,
    )


async def get_project(name: str) -> Optional[Project]:
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, priority, repos, env_file, created_at, modified_at FROM projects WHERE name = %s", (name,))
            row = cur.fetchone()

    if not row:
        return None
    repos_data = json.loads(row[3]) if row[3] else []
    return Project(
        id=row[0],
        name=row[1],
        priority=row[2],
        repos=[Repo(**r) for r in repos_data],
        env_file=row[4],
        created_at=row[5],
        modified_at=row[6],
    )


@activity.defn
async def list_projects() -> list[Project]:
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, priority, repos, env_file, created_at, modified_at FROM projects ORDER BY priority ASC")
            rows = cur.fetchall()

    return [
        Project(
            id=row[0],
            name=row[1],
            priority=row[2],
            repos=[Repo(**r) for r in json.loads(row[3] or "[]")],
            env_file=row[4],
            created_at=row[5],
            modified_at=row[6],
        )
        for row in rows
    ]


@activity.defn
async def get_project_repos(project_name: str) -> List[Repo]:
    project = await get_project(project_name)
    return project.repos if project else []


@activity.defn
async def get_project_env_file(project_name: str) -> str:
    project = await get_project(project_name)
    return project.env_file if project else ""


@activity.defn
async def save_project(
    name: str,
    priority: int = 5,
    repos: List[dict] = None,
    env_file: str = "",
) -> Project:
    return await store_project(name, priority, repos, env_file)