from environment.graders import EasyGrader, HardTaskGrader
from environment.models import EmailAction, EmailPriority
from environment.tasks import load_task_spec


def test_easy_grader_partial_credit_tracks_correct_labels():
    task = load_task_spec("easy")
    grader = EasyGrader(task.expected_outcomes)
    actions = [
        EmailAction(action_type="classify", email_id="easy-1", priority=EmailPriority.URGENT),
        EmailAction(action_type="classify", email_id="easy-2", priority=EmailPriority.SPAM),
        EmailAction(action_type="classify", email_id="easy-3", priority=EmailPriority.LOW),
    ]

    score = grader.score_partial(task.initial_emails, actions)
    assert round(score, 2) == 0.4


def test_hard_grader_rewards_prioritizing_urgent_before_low():
    task = load_task_spec("hard")
    grader = HardTaskGrader(task.expected_outcomes)

    urgent_first_actions = [
        EmailAction(
            action_type="respond",
            email_id="hard-1",
            priority=EmailPriority.URGENT,
            response_text="I am on it and will send an update today before 2 PM.",
        ),
        EmailAction(
            action_type="respond",
            email_id="hard-6",
            priority=EmailPriority.URGENT,
            response_text="We are investigating the incident now and I will share an update today.",
        ),
        EmailAction(action_type="archive", email_id="hard-5", priority=EmailPriority.LOW),
    ]
    low_first_actions = [
        EmailAction(action_type="archive", email_id="hard-5", priority=EmailPriority.LOW),
        EmailAction(
            action_type="respond",
            email_id="hard-1",
            priority=EmailPriority.URGENT,
            response_text="I am on it and will send an update today before 2 PM.",
        ),
        EmailAction(
            action_type="respond",
            email_id="hard-6",
            priority=EmailPriority.URGENT,
            response_text="We are investigating the incident now and I will share an update today.",
        ),
    ]

    urgent_first_score = grader.score_partial(task.initial_emails, urgent_first_actions)
    low_first_score = grader.score_partial(task.initial_emails, low_first_actions)

    assert urgent_first_score > low_first_score
