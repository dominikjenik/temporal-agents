"""Integration test: todo flow via HTTP endpoints — LLM mocked, real ephemeral DB.

Scenario: POST /request "nie teraz ale bude treba pridat dark mode do zbornika"
  → LLM resolves: intent=new_feature, project=zbornik, planning=todo
  → CommandDispatcher saves to project_requirements (status=todo)
  → GET /tasks returns the saved requirement
"""
from unittest.mock import AsyncMock, patch

from temporal_agents.intent_config import Intent, Planning, ParsedIntent, Project


async def test_todo_requirement_saved(http_client, ephemeral_db):
    """POST /request (todo) → requirement saved → GET /tasks returns it."""
    mock_parsed = ParsedIntent(
        intent=Intent.new_feature,
        project=Project.zbornik,
        planning=Planning.todo,
    )

    with patch(
        "temporal_agents.intent_parser._llm_resolve_and_parse",
        new_callable=AsyncMock,
        return_value=mock_parsed,
    ):
        response = await http_client.post(
            "/request",
            json={"message": "nie teraz ale bude treba pridat dark mode do zbornika"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "todo_saved"
    assert body["project"] == "zbornik"

    tasks_response = await http_client.get("/tasks")
    assert tasks_response.status_code == 200

    todos = [t for t in tasks_response.json() if t.get("status") == "todo"]
    assert len(todos) == 1
    assert todos[0]["project"] == "zbornik"
