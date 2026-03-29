"""Unit tests for capture_lesson activity — writes to DB (project='temporal', type='lesson')."""

from datetime import timedelta
from unittest.mock import patch

import aiosqlite
import pytest


# [temporal-3]
class TestCaptureLessonWritesToDB:
    """capture_lesson must insert a 'lesson' row into the tasks DB."""

    async def test_inserts_lesson_row(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch("temporal_agents.activities.lesson._db_path", return_value=db_file):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-123", "developer", "success", "Always write tests first")

        async with aiosqlite.connect(db_file) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM hitl WHERE type = 'lesson'")
            rows = await cursor.fetchall()

        assert len(rows) == 1
        assert rows[0]["project"] == "temporal"
        assert rows[0]["type"] == "lesson"
        assert "developer" in rows[0]["title"]
        assert "Always write tests first" in rows[0]["title"]
        assert rows[0]["workflow_id"] == "wf-123"


# [temporal-3]
class TestCaptureLessonHeartbeat:
    """capture_lesson must call activity.heartbeat() at least once."""

    async def test_heartbeat_called(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch("temporal_agents.activities.lesson._db_path", return_value=db_file):
            with patch("temporalio.activity.heartbeat") as mock_hb:
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-456", "tester", "failure", "Check edge cases")

        mock_hb.assert_called()


# [temporal-3]
class TestCaptureLessonOutcomeInTitle:
    """Outcome (success/failure) must appear uppercased in the task title."""

    @pytest.mark.parametrize("outcome", ["success", "failure"])
    async def test_outcome_in_title(self, tmp_path, outcome):
        db_file = str(tmp_path / "test.db")
        with patch("temporal_agents.activities.lesson._db_path", return_value=db_file):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-789", "devops-zbornik", outcome, "Deploy lesson")

        async with aiosqlite.connect(db_file) as db:
            cursor = await db.execute("SELECT title FROM hitl WHERE type = 'lesson'")
            row = await cursor.fetchone()

        assert outcome.upper() in row[0]


