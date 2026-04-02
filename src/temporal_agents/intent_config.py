from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class Intent(StrEnum):
    new_feature = "new_feature"
    chat = "chat"
    query = "query"


class Project(StrEnum):
    zbornik = "zbornik"
    ginidocs = "ginidocs"
    temporal_agentic_workflow = "temporal-agentic-workflow"


class Planning(StrEnum):
    todo = "todo"
    implementing = "implementing"


@dataclass
class ParsedIntent:
    intent: Intent
    project: Optional[Project] = None
    planning: Optional[Planning] = None


INTENTS = [i.value for i in Intent]
PROJECTS = [p.value for p in Project]
PLANNINGS = [p.value for p in Planning]
PROJECT_OPTIONAL_INTENTS = {Intent.chat, Intent.query}
