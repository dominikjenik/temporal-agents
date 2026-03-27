"""Unit tests for capture_lesson activity (PHASE5-001)."""

import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCaptureLessonAppendsToFile:
    """capture_lesson must append a lesson entry to pending.md."""

    async def test_appends_entry(self, tmp_path):
        pending = tmp_path / "pending.md"
        pending.write_text("# Pending Lessons\n\n## Lessons\n\n")

        with patch("temporal_agents.activities.lesson.PENDING_MD_PATH", pending):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-123", "developer", "success", "Always write tests first")

        content = pending.read_text()
        assert "wf-123" in content
        assert "developer" in content
        assert "success" in content
        assert "Always write tests first" in content


class TestCaptureLessonHeartbeat:
    """capture_lesson must call activity.heartbeat() at least once."""

    async def test_heartbeat_called(self, tmp_path):
        pending = tmp_path / "pending.md"
        pending.write_text("")

        with patch("temporal_agents.activities.lesson.PENDING_MD_PATH", pending):
            with patch("temporalio.activity.heartbeat") as mock_hb:
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-456", "tester", "failure", "Check edge cases")

        mock_hb.assert_called()


class TestCaptureLessonOutcomeValues:
    """Both success and failure outcomes must be correctly written."""

    @pytest.mark.parametrize("outcome", ["success", "failure"])
    async def test_outcome_written(self, tmp_path, outcome):
        pending = tmp_path / "pending.md"
        pending.write_text("")

        with patch("temporal_agents.activities.lesson.PENDING_MD_PATH", pending):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-789", "devops-zbornik", outcome, "Deploy lesson")

        content = pending.read_text()
        assert outcome in content


class TestCaptureLessonTimestampFormat:
    """Timestamp in the appended entry must match ISO 8601 UTC format."""

    async def test_timestamp_format(self, tmp_path):
        pending = tmp_path / "pending.md"
        pending.write_text("")

        with patch("temporal_agents.activities.lesson.PENDING_MD_PATH", pending):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.lesson import capture_lesson
                await capture_lesson("wf-ts", "developer", "success", "Timestamp test")

        content = pending.read_text()
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert re.search(pattern, content), f"No ISO 8601 timestamp found in:\n{content}"


class TestCaptureLessonOptions:
    """CAPTURE_LESSON_OPTIONS must have correct timeout and retry settings."""

    def test_options_values(self):
        from temporal_agents.activities.options import CAPTURE_LESSON_OPTIONS

        assert CAPTURE_LESSON_OPTIONS.schedule_to_close_timeout == timedelta(minutes=1)
        assert CAPTURE_LESSON_OPTIONS.retry_policy.maximum_attempts == 1
