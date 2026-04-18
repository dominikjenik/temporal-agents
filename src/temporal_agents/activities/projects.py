import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
import aiosqlite
import json
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


async def _init_db(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            priority INTEGER DEFAULT 5,
            repos TEXT DEFAULT '[]',
            env_file TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            modified_at TEXT NOT NULL
        )
    """)
    await db.commit()


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


@activity.defn
async def store_project(
    name: str,
    priority: int = 5,
    repos: List[dict] = None,
    env_file: str = "",
) -> Project:
    """Create or update a project."""
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    repos_json = "[]" if repos is None else json.dumps(repos)

    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT OR REPLACE INTO projects (id, name, priority, repos, env_file, created_at, modified_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record_id, name, priority, repos_json, env_file, now, now),
        )
        await db.commit()

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
    """Get project by name."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = await cursor.fetchone()

    if not row:
        return None

    repos_data = json.loads(row["repos"]) if row["repos"] else []

    return Project(
        id=row["id"],
        name=row["name"],
        priority=row["priority"],
        repos=[Repo(**r) for r in repos_data],
        env_file=row["env_file"],
        created_at=row["created_at"],
        modified_at=row["modified_at"],
    )


@activity.defn
async def list_projects() -> list[Project]:
    """List all projects."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM projects ORDER BY priority ASC")
        rows = await cursor.fetchall()

    return [
        Project(
            id=row["id"],
            name=row["name"],
            priority=row["priority"],
            repos=[Repo(**r) for r in json.loads(row["repos"] or "[]")],
            env_file=row["env_file"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
        )
        for row in rows
    ]


@activity.defn
async def get_project_repos(project_name: str) -> List[Repo]:
    """Activity wrapper for getting project repos."""
    project = await get_project(project_name)
    return project.repos if project else []


@activity.defn
async def get_project_env_file(project_name: str) -> str:
    """Activity wrapper for getting project env_file."""
    project = await get_project(project_name)
    return project.env_file if project else ""


@activity.defn
async def save_project(
    name: str,
    priority: int = 5,
    repos: List[dict] = None,
    env_file: str = "",
) -> Project:
    """Activity wrapper for store_project."""
    return await store_project(name, priority, repos, env_file)
