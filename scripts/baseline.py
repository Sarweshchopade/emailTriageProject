from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Protocol

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from environment.email_env import EmailTriageEnv
from environment.models import Email, EmailAction, EmailPriority, Observation

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


class Agent(Protocol):
    def act(self, observation: Observation) -> EmailAction:
        ...


class HeuristicAgent:
    PRIORITY_ORDER = {
        EmailPriority.URGENT: 3,
        EmailPriority.IMPORTANT: 2,
        EmailPriority.LOW: 1,
        EmailPriority.SPAM: 0,
    }

    def act(self, observation: Observation) -> EmailAction:
        email = self._choose_email(observation)
        priority = self._predict_priority(email)

        if observation.task_name == "easy":
            return EmailAction(action_type="classify", email_id=email.id, priority=priority)

        subject = f"{email.subject} {email.body}".casefold()
        if priority == EmailPriority.SPAM:
            return EmailAction(action_type="delete", email_id=email.id, priority=priority)
        if any(keyword in subject for keyword in ["security questionnaire", "security review", "compliance"]):
            return EmailAction(
                action_type="delegate",
                email_id=email.id,
                priority=priority,
                delegate_to="security@openenv.example",
                response_text="I am looping in security@openenv.example today and will follow up once they confirm the questionnaire details.",
            )
        if any(keyword in subject for keyword in ["invoice", "expense", "reimbursement", "billing"]):
            return EmailAction(
                action_type="delegate",
                email_id=email.id,
                priority=priority,
                delegate_to="finance@openenv.example",
                response_text="I am looping in finance@openenv.example to review the billing details and will share an update today.",
            )
        if any(keyword in subject for keyword in ["reschedule", "availability", "calendar", "onboarding session", "kickoff"]):
            return EmailAction(
                action_type="schedule",
                email_id=email.id,
                priority=priority,
                scheduled_time="Thursday 3:00 PM IST",
                response_text="Thursday 3:00 PM IST works on my side. I will send the updated calendar invite.",
            )
        if "next week" in subject:
            return EmailAction(
                action_type="snooze",
                email_id=email.id,
                priority=priority,
                snooze_until="2026-04-05T09:00:00+05:30",
                response_text="I have parked this for next week and will revisit it on 2026-04-05.",
            )
        if any(keyword in subject for keyword in ["photos", "newsletter", "weekly roundup", "water shutdown"]):
            return EmailAction(action_type="archive", email_id=email.id, priority=priority)

        return EmailAction(
            action_type="respond",
            email_id=email.id,
            priority=priority,
            response_text=self._compose_response(email),
        )

    def _choose_email(self, observation: Observation) -> Email:
        acted_on = {action.email_id for action in observation.action_history}
        candidates = [email for email in observation.current_emails if email.id not in acted_on]
        if not candidates:
            candidates = observation.current_emails

        return max(
            candidates,
            key=lambda email: (
                self.PRIORITY_ORDER[self._predict_priority(email)],
                email.timestamp,
            ),
        )

    def _predict_priority(self, email: Email) -> EmailPriority:
        text = f"{email.subject} {email.body}".casefold()
        if any(keyword in text for keyword in ["unsubscribe", "limited-time", "webinar", "promo", "sponsored offer"]):
            return EmailPriority.SPAM
        if any(keyword in text for keyword in ["urgent", "asap", "blocker", "today", "2 pm", "4 pm", "eod", "error spike"]):
            return EmailPriority.URGENT
        if any(
            keyword in text
            for keyword in [
                "awareness only",
                "no action needed",
                "photos",
                "newsletter",
                "weekly roundup",
                "shutdown",
                "next week",
            ]
        ):
            return EmailPriority.LOW
        if any(
            keyword in text
            for keyword in [
                "review",
                "roadmap",
                "contract",
                "questionnaire",
                "invoice",
                "billing",
                "reimbursement",
                "expense",
                "feedback",
                "kickoff",
                "onboarding",
                "security",
            ]
        ):
            return EmailPriority.IMPORTANT
        return EmailPriority.LOW

    @staticmethod
    def _compose_response(email: Email) -> str:
        text = f"{email.subject} {email.body}".casefold()
        if "export" in text or "launch blocker" in text:
            return "Thanks for flagging this. We are investigating the issue today and I will send an update by 4 PM."
        if "board" in text or "2 pm" in text:
            return "I am on it and will send an update today before 2 PM."
        if "error spike" in text or "incident" in text:
            return "We are investigating the incident now and I will share an update today as we narrow the root cause."
        if "feedback" in text:
            return "I will send my feedback today so the hiring team has it before EOD."
        return "Thanks for the note. I am on it and will send an update today."


class OpenAIAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when provider='openai'.")
        self.client = OpenAI(api_key=api_key)
        self.model = model or DEFAULT_OPENAI_MODEL

    def act(self, observation: Observation) -> EmailAction:
        parsed = self.client.responses.parse(
            model=self.model,
            instructions=(
                "You are an email triage assistant. "
                "Return exactly one valid EmailAction object that best advances the task."
            ),
            input=self._build_prompt(observation),
            text_format=EmailAction,
            temperature=0.1,
            max_output_tokens=300,
        )
        return parsed.output_parsed

    @staticmethod
    def _build_prompt(observation: Observation) -> str:
        emails_payload = [email.model_dump(mode="json") for email in observation.current_emails]
        history_payload = [action.model_dump(mode="json") for action in observation.action_history]
        return (
            f"Task name: {observation.task_name}\n"
            f"Task description: {observation.task_description}\n"
            f"Remaining actions: {observation.remaining_actions}\n"
            f"Current emails: {json.dumps(emails_payload, indent=2)}\n"
            f"Previous actions: {json.dumps(history_payload, indent=2)}\n"
            "Choose the single best next action."
        )


def build_agent(provider: str) -> Agent:
    if provider == "openai":
        return OpenAIAgent()
    return HeuristicAgent()


def run_episode(task_name: str, agent: Agent) -> Dict[str, object]:
    env = EmailTriageEnv(task_name=task_name)
    observation = env.reset()
    done = False
    last_reward = None

    while not done and observation.remaining_actions > 0:
        action = agent.act(observation)
        observation, reward, done, _ = env.step(action)
        last_reward = reward

    final_score = env.grader.final_score(env.action_history)
    return {
        "task": task_name,
        "score": final_score,
        "reward_delta": 0.0 if last_reward is None else last_reward.delta,
        "steps": env.steps_taken,
        "completed": done,
        "actions": [action.model_dump(mode="json") for action in env.action_history],
        "final_state": env.state(),
    }


def run_baseline(tasks: Iterable[str] | None = None, provider: str = "heuristic") -> Dict[str, object]:
    selected_tasks = list(tasks or ("easy", "medium", "hard"))
    agent = build_agent(provider)
    results = {task_name: run_episode(task_name, agent) for task_name in selected_tasks}

    with open("baseline_results.json", "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the baseline email triage agent.")
    parser.add_argument("--provider", choices=("heuristic", "openai"), default="heuristic")
    parser.add_argument("--tasks", nargs="*", default=["easy", "medium", "hard"])
    args = parser.parse_args()

    results = run_baseline(tasks=args.tasks, provider=args.provider)
    for task_name, payload in results.items():
        print(
            f"{task_name}: score={payload['score']:.2f} "
            f"steps={payload['steps']} completed={payload['completed']}"
        )


if __name__ == "__main__":
    main()
