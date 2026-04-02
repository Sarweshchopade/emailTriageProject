from environment.email_env import EmailTriageEnv
from environment.models import EmailAction, EmailPriority
from scripts.baseline import HeuristicAgent, run_episode


def test_reset_returns_initial_observation():
    env = EmailTriageEnv("easy")
    observation = env.reset()

    assert observation.task_name == "easy"
    assert len(observation.current_emails) == 5
    assert observation.remaining_actions == 10
    assert observation.action_history == []


def test_valid_classification_action_improves_score():
    env = EmailTriageEnv("easy")
    env.reset()

    _, reward, done, info = env.step(
        EmailAction(action_type="classify", email_id="easy-1", priority=EmailPriority.URGENT)
    )

    assert reward.score > 0.0
    assert reward.delta > 0.0
    assert done is False
    assert info["steps"] == 1


def test_invalid_action_ends_episode():
    env = EmailTriageEnv("easy")
    env.reset()

    _, reward, done, info = env.step(
        EmailAction(action_type="classify", email_id="missing-email", priority=EmailPriority.LOW)
    )

    assert done is True
    assert reward.breakdown["error"]
    assert "missing-email" in info["error"]


def test_easy_task_can_complete_perfectly():
    env = EmailTriageEnv("easy")
    env.reset()

    actions = [
        EmailAction(action_type="classify", email_id="easy-1", priority=EmailPriority.URGENT),
        EmailAction(action_type="classify", email_id="easy-2", priority=EmailPriority.SPAM),
        EmailAction(action_type="classify", email_id="easy-3", priority=EmailPriority.IMPORTANT),
        EmailAction(action_type="classify", email_id="easy-4", priority=EmailPriority.LOW),
        EmailAction(action_type="classify", email_id="easy-5", priority=EmailPriority.IMPORTANT),
    ]

    done = False
    reward = None
    for action in actions:
        _, reward, done, _ = env.step(action)

    assert done is True
    assert reward is not None
    assert reward.score == 1.0


def test_heuristic_agent_solves_all_tasks_reasonably_well():
    agent = HeuristicAgent()

    easy = run_episode("easy", agent)
    medium = run_episode("medium", agent)
    hard = run_episode("hard", agent)

    assert easy["score"] == 1.0
    assert medium["score"] >= 0.9
    assert hard["score"] >= 0.85
