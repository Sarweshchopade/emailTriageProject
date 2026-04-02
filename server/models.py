from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from environment.models import EmailPriority
from openenv.core.env_server.types import Action, Observation


class InboxEmail(BaseModel):
    id: str
    sender: str
    subject: str
    body: str
    timestamp: str
    thread_id: Optional[str] = None


class EmailTriageAction(Action):
    action_type: Literal[
        "classify",
        "archive",
        "delete",
        "respond",
        "delegate",
        "snooze",
        "schedule",
    ]
    email_id: str
    response_text: Optional[str] = None
    priority: Optional[EmailPriority] = None
    delegate_to: Optional[str] = None
    snooze_until: Optional[str] = None
    scheduled_time: Optional[str] = None
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def validate_payload(self) -> "EmailTriageAction":
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


class EmailTriageObservation(Observation):
    current_emails: List[InboxEmail] = Field(default_factory=list)
    action_history: List[EmailTriageAction] = Field(default_factory=list)
    remaining_actions: int = 0
    task_name: str = "easy"
    task_description: str = ""
