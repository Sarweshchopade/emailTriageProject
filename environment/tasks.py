from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from .models import ActionType, Email, EmailPriority

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ExpectedOutcome(BaseModel):
    email_id: str
    priority: Optional[EmailPriority] = None
    final_action: Optional[ActionType] = None
    response_keywords: List[str] = Field(default_factory=list)
    delegate_to: Optional[str] = None
    schedule_slot_contains: Optional[str] = None
    snooze_until_contains: Optional[str] = None
    weight: float = Field(default=1.0, gt=0.0)


class TaskSpec(BaseModel):
    name: str
    description: str
    max_steps: int = 20
    grader: str = "easy"
    initial_emails: List[Email]
    expected_outcomes: List[ExpectedOutcome]


def list_task_names() -> List[str]:
    return sorted(path.stem.replace("emails_", "") for path in DATA_DIR.glob("emails_*.json"))


def load_task_spec(task_name: str) -> TaskSpec:
    file_path = DATA_DIR / f"emails_{task_name}.json"
    if not file_path.exists():
        available = ", ".join(list_task_names())
        raise FileNotFoundError(f"Unknown task '{task_name}'. Available tasks: {available}")

    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return TaskSpec.model_validate(payload)
