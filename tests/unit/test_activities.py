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


# ---------------------------------------------------------------------------
# agents.py — wrapper activities pass correct agent_name
# ---------------------------------------------------------------------------

class TestDeveloperActivity:
    """developer_activity must pass agent_name='developer' to subprocess."""

    async def test_developer_activity(self):
        from temporal_agents.activities.agents import developer_activity

        fake_process = _make_fake_process(returncode=0, stdout_data=b"ok")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)) as mock_exec:
            with patch("temporalio.activity.heartbeat"):
                await developer_activity("implement feature X")

        args = mock_exec.call_args[0]
        assert any("developer" in str(arg) for arg in args), (
            f"Expected 'developer' in subprocess args, got: {args}"
        )


class TestTesterActivity:
    """tester_activity must pass agent_name='tester' to subprocess."""

    async def test_tester_activity(self):
        from temporal_agents.activities.agents import tester_activity

        fake_process = _make_fake_process(returncode=0, stdout_data=b"ok")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)) as mock_exec:
            with patch("temporalio.activity.heartbeat"):
                await tester_activity("run tests")

        args = mock_exec.call_args[0]
        assert any("tester" in str(arg) for arg in args), (
            f"Expected 'tester' in subprocess args, got: {args}"
        )


class TestDeveloperZborniokActivity:
    """developer_zbornik_activity must pass agent_name='developer-zbornik'."""

    async def test_developer_zbornik_activity(self):
        from temporal_agents.activities.agents import developer_zbornik_activity

        fake_process = _make_fake_process(returncode=0, stdout_data=b"ok")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)) as mock_exec:
            with patch("temporalio.activity.heartbeat"):
                await developer_zbornik_activity("build zbornik feature")

        args = mock_exec.call_args[0]
        assert any("developer-zbornik" in str(arg) for arg in args), (
            f"Expected 'developer-zbornik' in subprocess args, got: {args}"
        )


class TestDevopsZborniokActivity:
    """devops_zbornik_activity must pass agent_name='devops-zbornik'."""

    async def test_devops_zbornik_activity(self):
        from temporal_agents.activities.agents import devops_zbornik_activity

        fake_process = _make_fake_process(returncode=0, stdout_data=b"ok")

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)) as mock_exec:
            with patch("temporalio.activity.heartbeat"):
                await devops_zbornik_activity("deploy")

        args = mock_exec.call_args[0]
        assert any("devops-zbornik" in str(arg) for arg in args), (
            f"Expected 'devops-zbornik' in subprocess args, got: {args}"
        )


# ---------------------------------------------------------------------------
# options.py — schedule_to_close_timeout values
# ---------------------------------------------------------------------------

class TestActivityOptionsTimeouts:
    """Each activity options object must carry the correct schedule_to_close_timeout."""

    def test_activity_options_timeouts(self):
        from temporal_agents.activities.options import (
            DEVELOPER_OPTIONS,
            TESTER_OPTIONS,
            DEVELOPER_ZBORNIK_OPTIONS,
            DEVOPS_ZBORNIK_OPTIONS,
        )

        assert DEVELOPER_OPTIONS.schedule_to_close_timeout == timedelta(minutes=30), (
            "DEVELOPER_OPTIONS.schedule_to_close_timeout must be 30 minutes"
        )
        assert TESTER_OPTIONS.schedule_to_close_timeout == timedelta(minutes=10), (
            "TESTER_OPTIONS.schedule_to_close_timeout must be 10 minutes"
        )
        assert DEVELOPER_ZBORNIK_OPTIONS.schedule_to_close_timeout == timedelta(minutes=30), (
            "DEVELOPER_ZBORNIK_OPTIONS.schedule_to_close_timeout must be 30 minutes"
        )
        assert DEVOPS_ZBORNIK_OPTIONS.schedule_to_close_timeout == timedelta(minutes=20), (
            "DEVOPS_ZBORNIK_OPTIONS.schedule_to_close_timeout must be 20 minutes"
        )
