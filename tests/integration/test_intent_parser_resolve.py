"""LLM integration tests for POST /request endpoint.

Run only with --llm flag:
    uv run pytest tests/integration/test_intent_parser_resolve.py --llm

dispatch_command is mocked — no Temporal server required.
"""
import pytest
from unittest.mock import AsyncMock, patch

from temporal_agents.intent_config import Intent, Project


@pytest.mark.llm
async def test_pridaj_dark_mode_zbornik(http_client):
    """POST /request 'pridaj dark mode do zbornika' → new_feature / zbornik, dispatched."""
    with patch(
        "temporal_agents.intent_parser.dispatch_command",
        new_callable=AsyncMock,
        return_value={"type": "dispatched", "workflow_id": "mock-wf"},
    ) as mock_dispatch:
        response = await http_client.post(
            "/request", json={"message": "pridaj dark mode do zbornika"}
        )

    assert response.status_code == 200
    assert response.json()["type"] == "dispatched"

    parsed = mock_dispatch.call_args.args[0]
    assert parsed.intent == Intent.new_feature
    assert parsed.project == Project.zbornik


@pytest.mark.llm
async def test_ake_je_pocasie(http_client):
    """POST /request 'ake je pocasie?' → chat, never dispatched."""
    response = await http_client.post("/request", json={"message": "ake je pocasie?"})

    assert response.status_code == 200
    assert response.json()["type"] == "chat"


@pytest.mark.llm
async def test_chcel_by_som_pridat_button(http_client):
    """POST /request 'chcel by som pridat button' → clarification (project unknown)."""
    response = await http_client.post(
        "/request", json={"message": "chcel by som pridat button"}
    )

    assert response.status_code == 200
    assert response.json()["type"] == "clarification"
