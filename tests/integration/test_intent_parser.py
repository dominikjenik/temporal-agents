"""Integration tests for IntentParser — require claude CLI."""
import pytest

from temporal_agents.intent_parser import parse


@pytest.mark.integration
async def test_temporal_novy_button():
    """'temporal novy button' must resolve to new_feature / temporal-agentic-workflow."""
    result = await parse("temporal novy button")
    assert result.get("intent") == "new_feature"
    assert result.get("project") == "temporal-agentic-workflow"
