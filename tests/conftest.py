import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport


def pytest_addoption(parser):
    parser.addoption("--llm", action="store_true", default=False, help="Run tests that call a real LLM")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--llm"):
        skip = pytest.mark.skip(reason="requires --llm flag")
        for item in items:
            if item.get_closest_marker("llm"):
                item.add_marker(skip)


@pytest.fixture
def ephemeral_db(tmp_path, monkeypatch):
    """Ephemeral SQLite DB — patches hitl_db.DB_URL to an isolated temp file."""
    import temporal_agents.activities.hitl_db as hitl_db
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(hitl_db, "DB_URL", f"sqlite:///{db_file}")
    return db_file


@pytest.fixture
async def http_client():
    """FastAPI test client — Temporal startup mocked, no real server required."""
    from api.main import app

    with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
