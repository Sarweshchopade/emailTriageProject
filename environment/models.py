from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionType = Literal[
    "classify",
    "archive",
    "delete",
    "respond",
    "delegate",
    "snooze",
    "schedule",
]


class EmailPriority(str, Enum):
    URGENT = "urgent"
    IMPORTANT = "important"
    LOW = "low"
    SPAM = "spam"


class Email(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    sender: str
    subject: str
    body: str
    timestamp: str
    thread_id: Optional[str] = None


class EmailAction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    action_type: ActionType
    email_id: str
    response_text: Optional[str] = None
    priority: Optional[EmailPriority] = None
    delegate_to: Optional[str] = None
    snooze_until: Optional[str] = None
    scheduled_time: Optional[str] = None
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def validate_payload(self) -> "EmailAction":
        if self.action_type == "classify" and self.priority is None:
            raise ValueError("classify actions require a priority")
        if self.action_type == "respond" and not self.response_text:
            raise ValueError("respond actions require response_text")
        if self.action_type == "delegate" and not self.delegate_to:
            raise ValueError("delegate actions require delegate_to")
        if self.action_type == "snooze" and not self.snooze_until:
            raise ValueError("snooze actions require snooze_until")
        if self.action_type == "schedule" and not self.scheduled_time:
            raise ValueError("schedule actions require scheduled_time")
        return self


class Observation(BaseModel):
    current_emails: List[Email]
    action_history: List[EmailAction]
    remaining_actions: int
    task_name: str
    task_description: str


class Reward(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    delta: float = 0.0
    breakdown: Dict[str, Any] = Field(default_factory=dict)
