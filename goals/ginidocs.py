from typing import List

import tools.tool_registry as tool_registry
from models.tool_definitions import AgentGoal

goal_ginidocs = AgentGoal(
    id="goal_ginidocs",
    category_tag="web-dev",
    agent_name="GiniDocs Developer",
    agent_friendly_description="Implement backend or frontend features in GiniDocs and run pytest tests to verify them.",
    tools=[
        tool_registry.developer_tool,
        tool_registry.tester_tool,
    ],
    description="The user wants to add a feature or fix a bug in GiniDocs (FastAPI/Python backend, React/Next.js frontend). "
    "Help the user implement the change and then verify it with tests. "
    "Gather args for these tools in order: "
    "1. Developer: Implement the requested feature or bug fix. Ask which component (backend, frontend, or both) is affected and gather a detailed description before proceeding. "
    "2. Tester: Write and run pytest tests to verify the implementation. Always run tests after implementation to confirm correctness.",
    starter_prompt="Welcome! I'm your GiniDocs Developer agent. I can implement features and fixes across the GiniDocs stack — FastAPI/Python backend and React/Next.js frontend — and verify them with automated tests. What would you like me to implement?",
    example_conversation_history="\n ".join(
        [
            "user: I need a new API endpoint to export a document as PDF",
            "agent: Sure! I can add a PDF export endpoint to GiniDocs. Is this a backend-only change, or does it also require a frontend button to trigger the export?",
            "user: Both — a POST /api/documents/{id}/export endpoint on the backend and an Export button in the document toolbar on the frontend.",
            "agent: Got it. I'll implement the POST /api/documents/{id}/export endpoint in FastAPI and add an Export button to the document toolbar in Next.js.",
            "user_confirmed_tool_run: <user clicks confirm on Developer tool with component='both'>",
            "tool_result: { 'status': 'success', 'summary': 'Added POST /api/documents/{id}/export endpoint using WeasyPrint. Added ExportButton component to DocumentToolbar in Next.js.' }",
            "agent: Implementation complete! The backend endpoint and frontend button are ready. Shall I run tests to verify the new functionality?",
            "user: Yes, run the tests.",
            "user_confirmed_tool_run: <user clicks confirm on Tester tool>",
            "tool_result: { 'tests_run': 12, 'passed': 12, 'failed': 0, 'coverage': '87%', 'summary': 'All tests passed including test_export_document_as_pdf.' }",
            "agent: All 12 tests passed with 87% coverage. The PDF export feature is working correctly.",
        ]
    ),
)

ginidocs_goals: List[AgentGoal] = [
    goal_ginidocs,
]
