"""Integration tests — requires running Temporal server on localhost:7233."""
import pytest
import pytest_asyncio
from temporalio.client import Client


@pytest_asyncio.fixture
async def temporal_client():
    client = await Client.connect("localhost:7233")
    yield client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_temporal_server_connection(temporal_client):
    """Verify that client can connect to Temporal server."""
    workflows = temporal_client.list_workflows()
    assert workflows is not None
