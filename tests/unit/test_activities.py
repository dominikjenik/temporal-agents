"""Unit tests for the activities layer.

These tests are intentionally RED — production code does not exist yet.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_process(returncode: int = 0, stdout_data: bytes = b"done"):
    """Build a minimal mock that looks like asyncio.subprocess.Process."""
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout_data, b""))
    return process


# ---------------------------------------------------------------------------
# base.py — ClaudeActivityInput / ClaudeActivityOutput / run_claude_activity
# ---------------------------------------------------------------------------

class TestRunClaudeActivitySuccess:
    """run_claude_activity with returncode=0 must return success=True."""

    async def test_run_claude_activity_success(self):
        from temporal_agents.activities.base import (
            ClaudeActivityInput,
            run_claude_activity,
        )

        fake_process = _make_fake_process(returncode=0, stdout_data=b"done")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)):
            with patch("temporalio.activity.heartbeat"):
                result = await run_claude_activity(
                    ClaudeActivityInput(agent_name="developer", task="write tests")
                )

        assert result.success is True
        assert result.result == "done"
        assert result.exit_code == 0


class TestRunClaudeActivityFailure:
    """run_claude_activity with returncode=1 must return success=False."""

    async def test_run_claude_activity_failure(self):
        from temporal_agents.activities.base import (
            ClaudeActivityInput,
            run_claude_activity,
        )

        fake_process = _make_fake_process(returncode=1, stdout_data=b"error output")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)):
            with patch("temporalio.activity.heartbeat"):
                result = await run_claude_activity(
                    ClaudeActivityInput(agent_name="developer", task="write tests")
                )

        assert result.success is False
        assert result.exit_code == 1


class TestHeartbeatCalled:
    """activity.heartbeat() must be invoked at least once during subprocess run."""

    async def test_heartbeat_called(self):
        from temporal_agents.activities.base import (
            ClaudeActivityInput,
            run_claude_activity,
        )

        fake_process = _make_fake_process(returncode=0, stdout_data=b"ok")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)):
            with patch("temporalio.activity.heartbeat") as mock_heartbeat:
                await run_claude_activity(
                    ClaudeActivityInput(agent_name="developer", task="ping")
                )

        mock_heartbeat.assert_called()


