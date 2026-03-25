"""Unit tests for FeatureWorkflow and ProjectWorkflow.

These tests are intentionally RED — production code does not exist yet.
"""

import re
import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal_agents.activities.base import ClaudeActivityOutput
from temporal_agents.workflows import (
    FeatureInput,
    FeatureWorkflow,
    ProjectInput,
    ProjectWorkflow,
)


# ---------------------------------------------------------------------------
# Mock activities
# ---------------------------------------------------------------------------

@activity.defn(name="developer_activity")
async def mock_developer(task: str) -> ClaudeActivityOutput:
    return ClaudeActivityOutput(result="ok", success=True, exit_code=0)


@activity.defn(name="tester_activity")
async def mock_tester(task: str) -> ClaudeActivityOutput:
    return ClaudeActivityOutput(result="ok", success=True, exit_code=0)


@activity.defn(name="developer_zbornik_activity")
async def mock_developer_zbornik(task: str) -> ClaudeActivityOutput:
    return ClaudeActivityOutput(result="ok", success=True, exit_code=0)


@activity.defn(name="devops_zbornik_activity")
async def mock_devops_zbornik(task: str) -> ClaudeActivityOutput:
    return ClaudeActivityOutput(result="ok", success=True, exit_code=0)


# ---------------------------------------------------------------------------
# Scenario 1: FeatureWorkflow ginidocs — developer_activity AND tester_activity
# ---------------------------------------------------------------------------

class TestFeatureWorkflowGinidocs:
    """FeatureWorkflow with project_style='ginidocs' must call developer then tester."""

    async def test_calls_developer_and_tester_in_order(self):
        called = []

        @activity.defn(name="developer_activity")
        async def track_developer(task: str) -> ClaudeActivityOutput:
            called.append("developer")
            return ClaudeActivityOutput(result="ok", success=True, exit_code=0)

        @activity.defn(name="tester_activity")
        async def track_tester(task: str) -> ClaudeActivityOutput:
            called.append("tester")
            return ClaudeActivityOutput(result="ok", success=True, exit_code=0)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[FeatureWorkflow],
                activities=[track_developer, track_tester, mock_developer_zbornik, mock_devops_zbornik],
            ):
                await env.client.execute_workflow(
                    FeatureWorkflow.run,
                    FeatureInput(
                        project_style="ginidocs",
                        feature_name="auth",
                        description="add auth",
                    ),
                    id="ginidocs-order-test",
                    task_queue="test-workflows",
                )

        assert called == ["developer", "tester"], (
            f"Expected ['developer', 'tester'], got {called}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: FeatureWorkflow zbornik — ONLY developer_zbornik_activity
# ---------------------------------------------------------------------------

class TestFeatureWorkflowZbornik:
    """FeatureWorkflow with project_style='zbornik' must call ONLY developer_zbornik_activity."""

    async def test_calls_only_developer_zbornik(self):
        called = []

        @activity.defn(name="developer_activity")
        async def track_developer(task: str) -> ClaudeActivityOutput:
            called.append("developer")
            return ClaudeActivityOutput(result="ok", success=True, exit_code=0)

        @activity.defn(name="tester_activity")
        async def track_tester(task: str) -> ClaudeActivityOutput:
            called.append("tester")
            return ClaudeActivityOutput(result="ok", success=True, exit_code=0)

        @activity.defn(name="developer_zbornik_activity")
        async def track_developer_zbornik(task: str) -> ClaudeActivityOutput:
            called.append("developer_zbornik")
            return ClaudeActivityOutput(result="ok", success=True, exit_code=0)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[FeatureWorkflow],
                activities=[track_developer, track_tester, track_developer_zbornik, mock_devops_zbornik],
            ):
                await env.client.execute_workflow(
                    FeatureWorkflow.run,
                    FeatureInput(
                        project_style="zbornik",
                        feature_name="pdf",
                        description="fix pdf",
                    ),
                    id="zbornik-only-test",
                    task_queue="test-workflows",
                )

        assert called == ["developer_zbornik"], (
            f"Expected ['developer_zbornik'], got {called}"
        )


# ---------------------------------------------------------------------------
# Scenario 3: FeatureWorkflow get_status query == "completed"
# ---------------------------------------------------------------------------

class TestFeatureWorkflowGetStatus:
    """After completion, FeatureWorkflow.get_status query must return 'completed'."""

    async def test_get_status_returns_completed(self):
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[FeatureWorkflow],
                activities=[mock_developer, mock_tester, mock_developer_zbornik, mock_devops_zbornik],
            ):
                handle = await env.client.start_workflow(
                    FeatureWorkflow.run,
                    FeatureInput(
                        project_style="ginidocs",
                        feature_name="login",
                        description="add login",
                    ),
                    id="status-query-test",
                    task_queue="test-workflows",
                )
                await handle.result()
                status = await handle.query(FeatureWorkflow.get_status)

        assert status == "completed", (
            f"Expected 'completed', got '{status}'"
        )


# ---------------------------------------------------------------------------
# Scenario 4: ProjectWorkflow ginidocs — parallel execution
# ---------------------------------------------------------------------------

class TestProjectWorkflowGinidocsParallel:
    """ProjectWorkflow ginidocs must complete all features; get_feature_statuses returns all 'completed'."""

    async def test_all_features_completed(self):
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[ProjectWorkflow, FeatureWorkflow],
                activities=[mock_developer, mock_tester, mock_developer_zbornik, mock_devops_zbornik],
            ):
                handle = await env.client.start_workflow(
                    ProjectWorkflow.run,
                    ProjectInput(
                        project_style="ginidocs",
                        project_name="myapp",
                        features=["auth", "search", "export"],
                    ),
                    id="ginidocs-parallel-test",
                    task_queue="test-workflows",
                )
                await handle.result()
                statuses = await handle.query(ProjectWorkflow.get_feature_statuses)

        assert statuses == {
            "auth": "completed",
            "search": "completed",
            "export": "completed",
        }, f"Unexpected statuses: {statuses}"


# ---------------------------------------------------------------------------
# Scenario 5: ProjectWorkflow zbornik — sequential execution
# ---------------------------------------------------------------------------

class TestProjectWorkflowZborniokSequential:
    """ProjectWorkflow zbornik must complete all features sequentially; all 'completed'."""

    async def test_all_features_completed_sequentially(self):
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[ProjectWorkflow, FeatureWorkflow],
                activities=[mock_developer, mock_tester, mock_developer_zbornik, mock_devops_zbornik],
            ):
                handle = await env.client.start_workflow(
                    ProjectWorkflow.run,
                    ProjectInput(
                        project_style="zbornik",
                        project_name="zbornik",
                        features=["feat-a", "feat-b", "feat-c"],
                    ),
                    id="zbornik-sequential-test",
                    task_queue="test-workflows",
                )
                await handle.result()
                statuses = await handle.query(ProjectWorkflow.get_feature_statuses)

        assert set(statuses.values()) == {"completed"}, (
            f"Expected all 'completed', got: {statuses}"
        )
        assert set(statuses.keys()) == {"feat-a", "feat-b", "feat-c"}, (
            f"Unexpected feature keys: {statuses}"
        )


# ---------------------------------------------------------------------------
# Scenario 6: Dynamic IDs — two features must have different workflow IDs
# ---------------------------------------------------------------------------

class TestFeatureWorkflowDynamicIds:
    """Child workflow IDs must be unique and follow the format feature-{project}-{feature}-<uuid8>."""

    async def test_unique_workflow_ids(self):
        launched_ids: list[str] = []

        # Patch: we rely on the fact that if two child workflows had the same ID,
        # the second one would fail with WorkflowAlreadyStartedError.
        # Running successfully with two features proves IDs are distinct.
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-workflows",
                workflows=[ProjectWorkflow, FeatureWorkflow],
                activities=[mock_developer, mock_tester, mock_developer_zbornik, mock_devops_zbornik],
            ):
                handle = await env.client.start_workflow(
                    ProjectWorkflow.run,
                    ProjectInput(
                        project_style="ginidocs",
                        project_name="idtest",
                        features=["feat-x", "feat-y"],
                    ),
                    id="dynamic-ids-test",
                    task_queue="test-workflows",
                )
                await handle.result()
                statuses = await handle.query(ProjectWorkflow.get_feature_statuses)

        # Both completed — duplicate ID would have caused one to fail
        assert statuses == {"feat-x": "completed", "feat-y": "completed"}, (
            f"Unexpected statuses: {statuses}"
        )

    def test_id_format_matches_pattern(self):
        """ID format must be feature-{project_name}-{feature_name}-<uuid8>."""
        # This is a unit test for the ID generation helper.
        # The helper is expected to live at temporal_agents.workflows.make_feature_workflow_id
        from temporal_agents.workflows import make_feature_workflow_id

        result = make_feature_workflow_id(project_name="idtest", feature_name="feat-x")

        pattern = re.compile(r"^feature-idtest-feat-x-[0-9a-f]{8}$")
        assert pattern.match(result), (
            f"ID '{result}' does not match expected format 'feature-idtest-feat-x-<uuid8>'"
        )
