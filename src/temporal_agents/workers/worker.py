from temporal_agents.activities.agents import (
    developer_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    tester_activity,
)
from temporal_agents.activities.base import run_claude_activity
from temporal_agents.workflows import FeatureWorkflow, ProjectWorkflow

WORKFLOWS = [FeatureWorkflow, ProjectWorkflow]
ACTIVITIES = [
    developer_activity,
    tester_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    run_claude_activity,
]
