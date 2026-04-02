from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from environment.email_env import EmailTriageEnv
from environment.models import EmailAction
from environment.tasks import list_task_names, load_task_spec
from scripts.baseline import HeuristicAgent

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "static"
_SESSIONS: dict[str, EmailTriageEnv] = {}
_LOCK = Lock()
_HEURISTIC_AGENT = HeuristicAgent()


class SessionCreateRequest(BaseModel):
    task_name: str = "easy"


class SessionActionRequest(BaseModel):
    action: EmailAction


def _build_session_payload(session_id: str, env: EmailTriageEnv) -> dict[str, Any]:
    observation = env.observe()
    priority_hints = {
        email.id: _HEURISTIC_AGENT._predict_priority(email).value
        for email in observation.current_emails
    }

    recommended_action = None
    if not env.completed and observation.current_emails and observation.remaining_actions > 0:
        recommended_action = _HEURISTIC_AGENT.act(observation).model_dump(mode="json")

    return {
        "session_id": session_id,
        "task_name": env.task_name,
        "task_description": env.task_data.description,
        "max_steps": env.max_steps,
        "steps_taken": env.steps_taken,
        "remaining_actions": observation.remaining_actions,
        "current_score": env.current_score,
        "completed": env.completed,
        "resolved_count": len(env.task_data.initial_emails) - len(observation.current_emails),
        "total_emails": len(env.task_data.initial_emails),
        "progress_percent": round(env.current_score * 100, 1),
        "current_emails": [
            {
                **email.model_dump(mode="json"),
                "priority_hint": priority_hints[email.id],
            }
            for email in observation.current_emails
        ],
        "action_history": [action.model_dump(mode="json") for action in observation.action_history],
        "recommended_action": recommended_action,
    }


@router.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/ui/tasks", include_in_schema=False)
def get_tasks() -> list[dict[str, Any]]:
    return [
        {
            "name": task_name,
            "description": spec.description,
            "max_steps": spec.max_steps,
            "email_count": len(spec.initial_emails),
        }
        for task_name in list_task_names()
        for spec in [load_task_spec(task_name)]
    ]


@router.post("/ui/session", include_in_schema=False)
def create_session(request: SessionCreateRequest) -> dict[str, Any]:
    env = EmailTriageEnv(task_name=request.task_name)
    env.reset()
    session_id = str(uuid4())
    with _LOCK:
        _SESSIONS[session_id] = env
    return _build_session_payload(session_id, env)


@router.get("/ui/session/{session_id}", include_in_schema=False)
def get_session(session_id: str) -> dict[str, Any]:
    env = _SESSIONS.get(session_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _build_session_payload(session_id, env)


@router.post("/ui/session/{session_id}/action", include_in_schema=False)
def apply_action(session_id: str, request: SessionActionRequest) -> dict[str, Any]:
    env = _SESSIONS.get(session_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    _, reward, done, info = env.step(request.action)
    payload = _build_session_payload(session_id, env)
    payload["last_reward"] = reward.model_dump(mode="json")
    payload["done"] = done
    payload["info"] = info
    return payload
