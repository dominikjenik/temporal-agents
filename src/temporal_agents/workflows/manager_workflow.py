"""ManagerWorkflow — HITL orchestrator.

Flow:
  1. Calls manager_activity to generate an execution plan
  2. If require_confirm=True — waits for confirm signal
  3. Executes project via run_project_stub_activity (real agents TBD)
  4. Returns result

Signals: confirm(), cancel()
Queries: get_plan(), get_status()
"""
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import manager_activity, run_project_stub_activity

PLAN_TIMEOUT = timedelta(minutes=5)
EXEC_TIMEOUT = timedelta(minutes=60)


@dataclass
class ManagerInput:
    project: str
    task: str
    require_confirm: bool = True


@workflow.defn
class ManagerWorkflow:
    def __init__(self) -> None:
        self._confirmed: bool = False
        self._cancelled: bool = False
        self._status: str = "pending"
        self._plan: str = ""

    @workflow.run
    async def run(self, input: ManagerInput) -> str:
        # Step 1: Generate execution plan via manager agent
        self._status = "planning"
        workflow.logger.info(f"[Manager] Generating plan for project={input.project}")
        plan_result = await workflow.execute_activity(
            manager_activity,
            f"Project: {input.project}\nTask: {input.task}",
            start_to_close_timeout=PLAN_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        self._plan = (
            plan_result.result.strip()
            if plan_result.success
            else f"Project: {input.project}\nTask: {input.task}"
        )
        self._status = "plan_ready"
        workflow.logger.info(f"[Manager] Plan ready:\n{self._plan}")

        # Step 2: Wait for human confirmation if required
        if input.require_confirm:
            self._status = "waiting_confirm"
            workflow.logger.info("[Manager] Waiting for human confirmation...")
            await workflow.wait_condition(lambda: self._confirmed or self._cancelled)
            if self._cancelled:
                self._status = "cancelled"
                raise ApplicationError("Workflow cancelled by user", non_retryable=True)

        # Step 3: Execute (stub — real agent dispatch TBD)
        self._status = "running"
        workflow.logger.info(f"[Manager] Executing plan for project={input.project}")
        result = await workflow.execute_activity(
            run_project_stub_activity,
            args=[input.project, input.task],
            start_to_close_timeout=EXEC_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        self._status = "done"
        return result

    @workflow.signal
    async def confirm(self) -> None:
        workflow.logger.info("Signal received: confirm")
        self._confirmed = True

    @workflow.signal
    async def cancel(self) -> None:
        workflow.logger.info("Signal received: cancel")
        self._cancelled = True

    @workflow.query
    def get_plan(self) -> str:
        return self._plan

    @workflow.query
    def get_status(self) -> str:
        return self._status
