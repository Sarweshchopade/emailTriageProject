from __future__ import annotations

from typing import Any, Dict, Tuple

from .graders import get_grader
from .models import EmailAction, Observation, Reward
from .tasks import TaskSpec, load_task_spec


class EmailTriageEnv:
    TERMINAL_ACTIONS = {"archive", "delete", "respond", "delegate", "snooze", "schedule"}

    def __init__(self, task_name: str = "easy"):
        self.task_name = task_name
        self.task_data: TaskSpec = load_task_spec(task_name)
        self.grader = get_grader(self.task_data.grader, self.task_data.expected_outcomes)
        self.reset()

    def reset(self) -> Observation:
        self.all_emails = [email.model_copy(deep=True) for email in self.task_data.initial_emails]
        self.current_email_ids = [email.id for email in self.all_emails]
        self.action_history: list[EmailAction] = []
        self.steps_taken = 0
        self.max_steps = self.task_data.max_steps
        self.completed = False
        self.current_score = 0.0
        return self._get_observation()

    def step(self, action: EmailAction | Dict[str, Any]) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        parsed_action = action if isinstance(action, EmailAction) else EmailAction.model_validate(action)
        valid, error = self._is_valid_action(parsed_action)
        if not valid:
            self.completed = True
            reward = Reward(score=self.current_score, delta=0.0, breakdown={"error": error})
            return self._get_observation(), reward, True, {"error": error, "steps": self.steps_taken}

        previous_score = self.current_score
        self._apply_action(parsed_action)
        self.steps_taken += 1
        self.current_score = self._calculate_partial_score()
        reward = Reward(
            score=self.current_score,
            delta=self._compute_reward(previous_score, self.current_score),
            breakdown=self._get_score_breakdown(),
        )

        done = self._is_done()
        self.completed = done
        info = {
            "steps": self.steps_taken,
            "max_steps": self.max_steps,
            "completed": done,
            "final_score": self.grader.final_score(self.action_history),
            "resolved_emails": len(self.task_data.initial_emails) - len(self.current_email_ids),
        }
        return self._get_observation(), reward, done, info

    def state(self) -> Dict[str, Any]:
        return {
            "task": self.task_name,
            "description": self.task_data.description,
            "steps_taken": self.steps_taken,
            "max_steps": self.max_steps,
            "completed": self.completed,
            "current_score": self.current_score,
            "current_emails": [email.model_dump(mode="json") for email in self._current_emails()],
            "action_history": [action.model_dump(mode="json") for action in self.action_history],
        }

    def observe(self) -> Observation:
        return self._get_observation()

    def _current_emails(self):
        active_ids = set(self.current_email_ids)
        return [email for email in self.all_emails if email.id in active_ids]

    def _get_observation(self) -> Observation:
        return Observation(
            current_emails=self._current_emails(),
            action_history=list(self.action_history),
            remaining_actions=max(self.max_steps - self.steps_taken, 0),
            task_name=self.task_name,
            task_description=self.task_data.description,
        )

    def _is_valid_action(self, action: EmailAction) -> tuple[bool, str]:
        if action.email_id not in self.current_email_ids:
            return False, f"Email '{action.email_id}' is not available in the current inbox."
        return True, ""

    def _apply_action(self, action: EmailAction) -> None:
        self.action_history.append(action)
        if action.action_type in self.TERMINAL_ACTIONS and action.email_id in self.current_email_ids:
            self.current_email_ids.remove(action.email_id)

    def _calculate_partial_score(self) -> float:
        return self.grader.score_partial(self.task_data.initial_emails, self.action_history)

    def _compute_reward(self, previous_score: float, current_score: float) -> float:
        delta = max(0.0, current_score - previous_score)
        if self.steps_taken > self.max_steps * 0.8:
            delta = max(0.0, delta - 0.02)
        if self.grader.task_complete(self.action_history) and self.steps_taken <= self.max_steps:
            delta = min(1.0, delta + 0.05)
        return round(delta, 4)

    def _get_score_breakdown(self) -> Dict[str, Any]:
        breakdown = self.grader.breakdown(self.action_history)
        breakdown["remaining_actions"] = max(self.max_steps - self.steps_taken, 0)
        return breakdown

    def _is_done(self) -> bool:
        if self.steps_taken >= self.max_steps:
            return True
        if self.grader.final_score(self.action_history) >= 0.999:
            return True
        return self.grader.task_complete(self.action_history)
