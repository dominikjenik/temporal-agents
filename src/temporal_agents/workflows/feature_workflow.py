from dataclasses import dataclass
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import (
        developer_activity,
        developer_zbornik_activity,
        tester_activity,
    )
    from temporal_agents.activities.options import (
        DEVELOPER_OPTIONS,
        DEVELOPER_ZBORNIK_OPTIONS,
        TESTER_OPTIONS,
    )


@dataclass
class FeatureInput:
    project_style: str   # "ginidocs" alebo "zbornik"
    feature_name: str
    description: str


@workflow.defn
class FeatureWorkflow:
    def __init__(self) -> None:
        self._status: str = "pending"

    @workflow.run
    async def run(self, input: FeatureInput) -> str:
        self._status = "running"

        if input.project_style == "ginidocs":
            # Step 1: developer_activity, then Step 2: tester_activity
            await workflow.execute_activity(
                developer_activity,
                input.description,
                schedule_to_close_timeout=DEVELOPER_OPTIONS.schedule_to_close_timeout,
                retry_policy=DEVELOPER_OPTIONS.retry_policy,
            )
            await workflow.execute_activity(
                tester_activity,
                input.description,
                schedule_to_close_timeout=TESTER_OPTIONS.schedule_to_close_timeout,
                retry_policy=TESTER_OPTIONS.retry_policy,
            )
        elif input.project_style == "zbornik":
            # Only developer_zbornik_activity — no separate tester step
            await workflow.execute_activity(
                developer_zbornik_activity,
                input.description,
                schedule_to_close_timeout=DEVELOPER_ZBORNIK_OPTIONS.schedule_to_close_timeout,
                retry_policy=DEVELOPER_ZBORNIK_OPTIONS.retry_policy,
            )

        self._status = "completed"
        return self._status

    @workflow.query
    def get_status(self) -> str:
        return self._status
