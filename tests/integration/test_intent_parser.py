"""Integration tests for intent_parser_resolve — kept for backward compat naming."""
import pytest

from temporal_agents.intent_parser import intent_parser_resolve


@pytest.mark.integration
async def test_temporal_novy_button():
    """'temporal novy button' must resolve to new_feature / temporal-agentic-workflow."""
    from unittest.mock import AsyncMock, patch
    with patch("temporal_agents.intent_parser.dispatch_command", new_callable=AsyncMock) as mock_dispatch:
        mock_dispatch.return_value = "mock-wf-id"
        result = await intent_parser_resolve("temporal novy button", client=None)

    assert result.get("type") == "dispatched"
    parsed = mock_dispatch.call_args.args[0]
    assert parsed.intent == "new_feature"
    assert parsed.project == "temporal-agentic-workflow"
