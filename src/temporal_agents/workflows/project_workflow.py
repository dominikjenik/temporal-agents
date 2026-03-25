import asyncio
import uuid
from dataclasses import dataclass, field
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal_agents.workflows.feature_workflow import FeatureInput, FeatureWorkflow


def make_feature_workflow_id(
    project_name: str,
    feature_name: str,
    uid_hex: str | None = None,
) -> str:
    """Generate a unique workflow ID for a feature child workflow.

    uid_hex — pre-computed 8-char hex string. When None (e.g. in unit tests
    outside a workflow event loop), falls back to stdlib uuid.uuid4().
    Inside a workflow, callers must pass workflow.uuid4().hex[:8] to maintain
    Temporal's determinism requirement.
    """
    suffix = uid_hex if uid_hex is not None else uuid.uuid4().hex[:8]
    return f"feature-{project_name}-{feature_name}-{suffix}"


@dataclass
class ProjectInput:
    project_style: str   # "ginidocs" alebo "zbornik"
    project_name: str
    features: list[str]


@workflow.defn
class ProjectWorkflow:
    def __init__(self) -> None:
        self._feature_statuses: dict[str, str] = {}

    @workflow.run
    async def run(self, input: ProjectInput) -> dict[str, str]:
        if input.project_style == "ginidocs":
            # Parallel execution: start all child workflows at once
            tasks = []
            for feature_name in input.features:
                # Use workflow.uuid4() for Temporal-safe deterministic IDs
                workflow_id = make_feature_workflow_id(
                    input.project_name,
                    feature_name,
                    uid_hex=workflow.uuid4().hex[:8],
                )
                self._feature_statuses[feature_name] = "pending"
                tasks.append(
                    workflow.execute_child_workflow(
                        FeatureWorkflow.run,
                        FeatureInput(
                            project_style=input.project_style,
                            feature_name=feature_name,
                            description=feature_name,
                        ),
                        id=workflow_id,
                    )
                )
            results = await asyncio.gather(*tasks)
            for feature_name, status in zip(input.features, results):
                self._feature_statuses[feature_name] = status
        else:
            # Sequential execution (zbornik and default)
            for feature_name in input.features:
                workflow_id = make_feature_workflow_id(
                    input.project_name,
                    feature_name,
                    uid_hex=workflow.uuid4().hex[:8],
                )
                self._feature_statuses[feature_name] = "pending"
                status = await workflow.execute_child_workflow(
                    FeatureWorkflow.run,
                    FeatureInput(
                        project_style=input.project_style,
                        feature_name=feature_name,
                        description=feature_name,
                    ),
                    id=workflow_id,
                )
                self._feature_statuses[feature_name] = status

        return self._feature_statuses

    @workflow.query
    def get_feature_statuses(self) -> dict[str, str]:
        return self._feature_statuses
