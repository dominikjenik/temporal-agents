from typing import List

import tools.tool_registry as tool_registry
from models.tool_definitions import AgentGoal

goal_zbornik = AgentGoal(
    id="goal_zbornik",
    category_tag="mobile-dev",
    agent_name="Zborník Developer",
    agent_friendly_description="Implement features or fix bugs in the ZBORNIK_APP mobile application, then build and deploy.",
    tools=[
        tool_registry.developer_zbornik_tool,
        tool_registry.devops_zbornik_tool,
    ],
    description="The user wants to add a feature or fix a bug in the ZBORNIK_APP React Native / Expo mobile PDF viewer application. "
    "Help the user implement the change and then build and deploy it. "
    "Gather args for these tools in order: "
    "1. DeveloperZbornik: Implement the requested feature or bug fix in ZBORNIK_APP. Ask the user to describe the change in detail before proceeding. "
    "2. DevopsZbornik: Build and deploy the app after the implementation is confirmed. Only proceed when the user explicitly asks to build and deploy.",
    starter_prompt="Welcome! I'm your Zborník Developer agent. I can implement features and fixes in the ZBORNIK_APP mobile application (a React Native / Expo PDF viewer), and then build and deploy the updated app. What would you like me to implement?",
    example_conversation_history="\n ".join(
        [
            "user: I'd like to add a dark mode toggle to the PDF viewer",
            "agent: Great! I can implement a dark mode toggle for the ZBORNIK_APP PDF viewer. Could you describe where you'd like the toggle to appear (e.g., in the toolbar, settings screen) and any specific behaviour you expect?",
            "user: In the toolbar, top right corner. It should invert the PDF colours.",
            "agent: Understood. I'll implement a dark mode toggle in the top-right toolbar that inverts PDF colours when activated.",
            "user_confirmed_tool_run: <user clicks confirm on DeveloperZbornik tool>",
            "tool_result: { 'status': 'success', 'summary': 'Added DarkModeToggle component to toolbar. Uses CSS invert filter on the PDF WebView. State persisted in AsyncStorage.' }",
            "agent: The dark mode toggle has been implemented and added to the top-right toolbar. The feature inverts PDF colours and remembers your preference. Would you like me to build and deploy the updated app?",
            "user: Yes, please build and deploy.",
            "user_confirmed_tool_run: <user clicks confirm on DevopsZbornik tool>",
            "tool_result: { 'build_status': 'success', 'deploy_status': 'success', 'apk_path': 'build/zbornik.apk' }",
            "agent: The app has been successfully built and deployed. The new APK with the dark mode feature is ready.",
        ]
    ),
)

zbornik_goals: List[AgentGoal] = [
    goal_zbornik,
]
