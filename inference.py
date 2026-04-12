from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from environment.email_env import EmailTriageEnv
from environment.models import EmailAction, Observation
from scripts.baseline import HeuristicAgent

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
HF_TOKEN = os.getenv("HF_TOKEN", "")
TASKS = ("easy", "medium", "hard")
BENCHMARK = "email-triage-assistant"
TEMPERATURE = 0.0
MAX_COMPLETION_TOKENS = 350
SUCCESS_SCORE_THRESHOLD = 0.1
STRICT_MIN_SCORE = 0.001
STRICT_MAX_SCORE = 0.999


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    return json.loads(text[start : end + 1])


class SubmissionAgent:
    def __init__(self) -> None:
        self.fallback = HeuristicAgent()
        self.client = None
        self.source = "heuristic"
        self.last_error = ""

        if HF_TOKEN and OpenAI is not None:
            try:
                self.client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
            except Exception as exc:  # pragma: no cover
                self.last_error = str(exc)

    @property
    def provider_name(self) -> str:
        return "openai" if self.client is not None else "heuristic_fallback"

    def act(self, observation: Observation) -> EmailAction:
        if self.client is None:
            self.source = "heuristic"
            self.last_error = ""
            return self.fallback.act(observation)

        try:
            completion = self.client.chat.completions.create(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                max_tokens=MAX_COMPLETION_TOKENS,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an email triage assistant. "
                            "Return exactly one JSON object matching this schema: "
                            "{action_type,email_id,response_text,priority,delegate_to,snooze_until,scheduled_time,rationale}. "
                            "Only include fields that are needed."
                        ),
                    },
                    {"role": "user", "content": self._build_prompt(observation)},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            action_dict = _extract_json_object(content)
            action = EmailAction.model_validate(action_dict)
            self.source = "openai"
            self.last_error = ""
            return action
        except Exception as exc:  # pragma: no cover
            self.source = "heuristic"
            self.last_error = str(exc)
            return self.fallback.act(observation)

    @staticmethod
    def _build_prompt(observation: Observation) -> str:
        current_emails = [email.model_dump(mode="json") for email in observation.current_emails]
        action_history = [action.model_dump(mode="json") for action in observation.action_history]
        return (
            f"Task name: {observation.task_name}\n"
            f"Task description: {observation.task_description}\n"
            f"Remaining actions: {observation.remaining_actions}\n"
            f"Current emails: {json.dumps(current_emails, ensure_ascii=True)}\n"
            f"Action history: {json.dumps(action_history, ensure_ascii=True)}\n"
            "Choose the single best next action."
        )


def _format_action(action: EmailAction) -> str:
    parts = [f"action_type={action.action_type}", f"email_id={action.email_id}"]
    if action.priority:
        parts.append(f"priority={action.priority}")
    if action.delegate_to:
        parts.append(f"delegate_to={action.delegate_to}")
    if action.scheduled_time:
        parts.append(f"scheduled_time={action.scheduled_time}")
    if action.snooze_until:
        parts.append(f"snooze_until={action.snooze_until}")
    return ";".join(parts)


def _strict_score(value: float) -> float:
    if value <= 0.0:
        return STRICT_MIN_SCORE
    if value >= 1.0:
        return STRICT_MAX_SCORE
    return round(value, 4)


def run_task(task_name: str, agent: SubmissionAgent) -> dict[str, Any]:
    started_at = time.time()
    rewards: list[float] = []
    steps_taken = 0
    final_score = STRICT_MIN_SCORE
    success = False
    completed = False
    error_message: Optional[str] = None

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        env = EmailTriageEnv(task_name=task_name)
        observation = env.reset()
        done = False

        while not done and observation.remaining_actions > 0:
            action = agent.act(observation)
            observation, reward, done, info = env.step(action)
            step_reward = float(reward.delta)
            rewards.append(step_reward)
            steps_taken = env.steps_taken
            error = info.get("error") if isinstance(info, dict) else None
            log_step(
                step=steps_taken,
                action=_format_action(action),
                reward=step_reward,
                done=done,
                error=error,
            )

        final_score = _strict_score(float(env.grader.final_score(env.action_history)))
        completed = done
        success = final_score >= SUCCESS_SCORE_THRESHOLD
        duration_s = round(time.time() - started_at, 3)
        return {
            "task": task_name,
            "score": round(final_score, 4),
            "steps": steps_taken,
            "completed": completed,
            "duration_s": duration_s,
            "provider": agent.provider_name,
        }
    except Exception as exc:  # pragma: no cover
        error_message = str(exc)
        success = False
        duration_s = round(time.time() - started_at, 3)
        return {
            "task": task_name,
            "score": round(final_score, 4),
            "steps": steps_taken,
            "completed": completed,
            "duration_s": duration_s,
            "provider": agent.provider_name,
            "error": error_message,
        }
    finally:
        log_end(success=success, steps=steps_taken, score=_strict_score(final_score), rewards=rewards)


def main() -> None:
    agent = SubmissionAgent()
    results = [run_task(task_name, agent) for task_name in TASKS]
    summary = {
        "tasks": results,
        "average_score": _strict_score(sum(item["score"] for item in results) / len(results)),
        "provider": agent.provider_name,
    }
    with open("inference_results.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
