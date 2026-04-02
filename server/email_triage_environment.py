from __future__ import annotations

from uuid import uuid4

from environment.email_env import EmailTriageEnv
from environment.models import EmailAction
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata, State

from .models import EmailTriageAction, EmailTriageObservation, InboxEmail


class OpenEnvEmailTriageEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self, task_name: str = "easy"):
        super().__init__()
        self._task_name = task_name
        self._env = EmailTriageEnv(task_name=task_name)
        self._state = State(episode_id=str(uuid4()), step_count=0)

    def reset(self, seed=None, episode_id=None, **kwargs) -> EmailTriageObservation:
        task_name = kwargs.get("task_name", self._task_name)
        if task_name != self._env.task_name:
            self._task_name = task_name
            self._env = EmailTriageEnv(task_name=task_name)

        observation = self._env.reset()
        self._state = State(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_name=self._env.task_name,
            current_score=self._env.current_score,
        )
        return self._convert_observation(observation, reward=0.0, done=False)

    def step(self, action: EmailTriageAction, timeout_s=None, **kwargs) -> EmailTriageObservation:
        internal_action = EmailAction(
            action_type=action.action_type,
            email_id=action.email_id,
            response_text=action.response_text,
            priority=action.priority,
            delegate_to=action.delegate_to,
            snooze_until=action.snooze_until,
            scheduled_time=action.scheduled_time,
            rationale=action.rationale,
        )
        observation, reward, done, info = self._env.step(internal_action)
        self._state.step_count = self._env.steps_taken
        self._state.episode_id = self._state.episode_id or str(uuid4())
        self._state.task_name = self._env.task_name
        self._state.current_score = self._env.current_score
        return self._convert_observation(
            observation,
            reward=reward.score,
            done=done,
            metadata={
                **info,
                "reward_delta": reward.delta,
                "breakdown": reward.breakdown,
            },
        )

    @property
    def state(self) -> State:
        return State(
            episode_id=self._state.episode_id,
            step_count=self._env.steps_taken,
            task_name=self._env.task_name,
            current_score=self._env.current_score,
        )

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="email-triage-assistant",
            description=self._env.task_data.description,
            version="1.0.0",
            author="Codex",
        )

    @staticmethod
    def _convert_observation(
        observation,
        *,
        reward: float,
        done: bool,
        metadata: dict | None = None,
    ) -> EmailTriageObservation:
        return EmailTriageObservation(
            current_emails=[InboxEmail(**email.model_dump()) for email in observation.current_emails],
            action_history=[
                EmailTriageAction(**action.model_dump(exclude={"metadata"}))
                for action in observation.action_history
            ],
            remaining_actions=observation.remaining_actions,
            task_name=observation.task_name,
            task_description=observation.task_description,
            done=done,
            reward=reward,
            metadata=metadata or {},
        )
