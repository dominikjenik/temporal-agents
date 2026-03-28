"""CommandDispatcher — plain Python router that maps parsed intent to the correct Temporal workflow."""
from temporal_agents.workflows.feature_workflow import FeatureInput, FeatureWorkflow


def dispatch(intent: str, project: str, user_message: str):
    """Return (workflow_class, workflow_input) for the given intent, or raise ValueError."""
    if intent == "new_feature":
        return FeatureWorkflow, FeatureInput(project=project, user_message=user_message)
    if intent == "new_project":
        raise NotImplementedError(f"new_project workflow not implemented yet")
    raise ValueError(f"Unknown intent: '{intent}'. Supported: new_feature, new_project.")
