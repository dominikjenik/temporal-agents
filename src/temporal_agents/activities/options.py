from dataclasses import dataclass
from datetime import timedelta

from temporalio.common import RetryPolicy


@dataclass
class ActivityOptions:
    """Typed container for activity execution options.

    Attributes mirror the keys accepted by temporalio.workflow.ActivityConfig so
    callers can unpack with **dataclasses.asdict(options) when needed.
    """

    schedule_to_close_timeout: timedelta
    retry_policy: RetryPolicy


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
