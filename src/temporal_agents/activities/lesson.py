from datetime import datetime, timezone
from pathlib import Path

from temporalio import activity

# Module-level constant — patchable in tests
PENDING_MD_PATH = Path(__file__).parent.parent.parent.parent.parent / "lessons" / "pending.md"


@activity.defn
async def capture_lesson(
    workflow_id: str,
    agent_type: str,
    outcome: str,
    lesson_text: str,
) -> None:
    """Append a lesson learned to lessons/pending.md."""
    activity.heartbeat()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = (
        f"\n### {timestamp}\n"
        f"- **workflow_id**: {workflow_id}\n"
        f"- **agent_type**: {agent_type}\n"
        f"- **outcome**: {outcome}\n"
        f"- **lesson_text**: {lesson_text}\n"
        f"\n---\n"
    )

    with open(PENDING_MD_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
