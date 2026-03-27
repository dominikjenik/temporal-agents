"""Integration tests for temporal-agents — requires running Temporal server on localhost:7233."""
import asyncio
import pytest
import pytest_asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import activity

from temporal_agents.activities.base import ClaudeActivityOutput
from temporal_agents.workflows.feature_workflow import FeatureWorkflow, FeatureInput


# ============================================================
# Mock activities (same names as real ones — used by Worker)
# Activities accept str (description), not ClaudeActivityInput
# ============================================================

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


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def temporal_client():
    """Real Temporal client connected to localhost:7233."""
    client = await Client.connect("localhost:7233")
    yield client


# ============================================================
# Tests
# ============================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_temporal_server_connection(temporal_client):
    """Verify that client can connect to Temporal server."""
    # list_workflows() is a lazy generator — calling it verifies connectivity
    # without requiring any workflows to exist
    workflows = temporal_client.list_workflows()
    assert workflows is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feature_workflow_ginidocs_end_to_end(temporal_client):
    """End-to-end test: FeatureWorkflow with ginidocs style using mock activities."""
    task_queue = "integration-test-queue"

    mock_activities = [
        mock_developer,
        mock_tester,
        mock_developer_zbornik,
        mock_devops_zbornik,
    ]

    async with Worker(
        temporal_client,
        task_queue=task_queue,
        workflows=[FeatureWorkflow],
        activities=mock_activities,
    ):
        result = await temporal_client.execute_workflow(
            FeatureWorkflow.run,
            FeatureInput(
                project_style="ginidocs",
                feature_name="test-feature",
                description="Test feature description",
            ),
            id=f"integration-test-{asyncio.get_event_loop().time()}",
            task_queue=task_queue,
        )
        assert result == "completed"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="ManagerWorkflow not yet implemented")
async def test_manager_workflow_hitl_signal(temporal_client):
    """Test HITL confirm signal flow for ManagerWorkflow."""
    pass
