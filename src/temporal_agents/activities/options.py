from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from temporalio.common import RetryPolicy


@dataclass
class ActivityOptions:
    """Typed container for activity execution options.

    Attributes mirror the keys accepted by temporalio.workflow.ActivityConfig so
    callers can unpack with **dataclasses.asdict(options) when needed.

    Either schedule_to_close_timeout or start_to_close_timeout must be set.
    """

    retry_policy: RetryPolicy
    schedule_to_close_timeout: Optional[timedelta] = None
    start_to_close_timeout: Optional[timedelta] = None


DEVELOPER_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=30),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

TESTER_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=10),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

DEVELOPER_ZBORNIK_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=30),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

DEVOPS_ZBORNIK_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=20),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

CAPTURE_LESSON_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=1),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

STORE_TASK_OPTIONS = ActivityOptions(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(maximum_attempts=3),
)

EXECUTE_DB_QUERY_OPTIONS = ActivityOptions(
    start_to_close_timeout=timedelta(seconds=10),
    retry_policy=RetryPolicy(maximum_attempts=2),
)

MANAGER_OPTIONS = ActivityOptions(
    schedule_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(
        maximum_attempts=1,
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
    ),
)

RUN_STUB_OPTIONS = ActivityOptions(
    start_to_close_timeout=timedelta(seconds=10),
    retry_policy=RetryPolicy(maximum_attempts=1),
)

RUN_CHAT_OPTIONS = ActivityOptions(
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(maximum_attempts=2),
)
