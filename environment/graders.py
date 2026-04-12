from __future__ import annotations

from typing import Iterable, List, Dict
from typing import Iterable, List

from .models import Email, EmailAction, EmailPriority
from .tasks import ExpectedOutcome


class EmailGrader:
    @staticmethod 
    def normalize_score(score: float) -> float:
        if score <= 0:
            return 0.01
        if score >= 1:
            return 0.99
        return score
    def __init__(self, expected_actions: Iterable[ExpectedOutcome]):
        self.expected = list(expected_actions)

    def score_partial(self, emails: List[Email], actions: List[EmailAction]) -> float:
        if not self.expected:
            return 0.99

        total_weight = sum(expectation.weight for expectation in self.expected)
        achieved = sum(
            self._score_expectation(expectation, actions) * expectation.weight
            for expectation in self.expected
        )
        return round(self.normalize_score(achieved / total_weight), 4)

    def final_score(self, actions: List[EmailAction]) -> float:
        return self.score_partial([], actions)

    def task_complete(self, actions: List[EmailAction]) -> bool:
        return all(self._core_action_completed(expectation, actions) for expectation in self.expected)

    def breakdown(self, actions: List[EmailAction]) -> Dict[str, float]:
        per_email = {
            expectation.email_id: round(self._score_expectation(expectation, actions), 4)
            for expectation in self.expected
        }
        per_email["overall"] = round(self.final_score(actions), 4)
        return per_email

    def _core_action_completed(self, expectation: ExpectedOutcome, actions: List[EmailAction]) -> bool:
        email_actions = self._actions_for_email(actions, expectation.email_id)
        if not email_actions:
            return False

        if expectation.final_action == "classify":
            return any(
                action.action_type == "classify"
                and (expectation.priority is None or action.priority == expectation.priority)
                for action in email_actions
            )

        if expectation.final_action:
            return any(action.action_type == expectation.final_action for action in email_actions)

        if expectation.priority:
            return any(action.priority == expectation.priority for action in email_actions)

        return bool(email_actions)

    def _score_expectation(self, expectation: ExpectedOutcome, actions: List[EmailAction]) -> float:
        email_actions = self._actions_for_email(actions, expectation.email_id)
        if not email_actions:
            return 0.01

        checks: List[tuple[float, float]] = []

        if expectation.priority is not None:
            matched_priority = any(action.priority == expectation.priority for action in email_actions)
            checks.append((0.25, 0.9 if matched_priority else 0.1))

        if expectation.final_action is not None:
            matched_action = any(action.action_type == expectation.final_action for action in email_actions)
            checks.append((0.35, 0.9 if matched_action else 0.1))

        if expectation.delegate_to:
            needle = expectation.delegate_to.casefold()
            matched_delegate = any(
                action.delegate_to and action.delegate_to.casefold() == needle
                for action in email_actions
            )
            checks.append((0.15, 0.9 if matched_delegate else 0.1))

        if expectation.schedule_slot_contains:
            needle = expectation.schedule_slot_contains.casefold()
            matched_schedule = any(
                action.scheduled_time and needle in action.scheduled_time.casefold()
                for action in email_actions
            )
            checks.append((0.15, 0.9 if matched_schedule else 0.1))

        if expectation.snooze_until_contains:
            needle = expectation.snooze_until_contains.casefold()
            matched_snooze = any(
                action.snooze_until and needle in action.snooze_until.casefold()
                for action in email_actions
            )
            checks.append((0.15, 0.9 if matched_snooze else 0.1))

        if expectation.response_keywords:
            response_score = max(
                (
                    self._keyword_coverage(action.response_text or "", expectation.response_keywords)
                    for action in email_actions
                ),
                default=0.1,
            )
            checks.append((0.25, response_score))

        if not checks:
            return 0.99

        total_weight = sum(weight for weight, _ in checks)
        return self.normalize_score(sum(weight * score for weight, score in checks) / total_weight)

    @staticmethod
    def _actions_for_email(actions: List[EmailAction], email_id: str) -> List[EmailAction]:
        return [action for action in actions if action.email_id == email_id]

    @staticmethod
    def _keyword_coverage(text: str, keywords: List[str]) -> float:
        if not keywords:
            return 0.99

        haystack = text.casefold()
        matched = sum(1 for keyword in keywords if keyword.casefold() in haystack)
        return matched / len(keywords)


class EasyGrader(EmailGrader):
    def _score_expectation(self, expectation: ExpectedOutcome, actions: List[EmailAction]) -> float:
        if expectation.final_action == "classify" and expectation.priority is not None:
            email_actions = self._actions_for_email(actions, expectation.email_id)
            return 0.9 if any(
                action.action_type == "classify" and action.priority == expectation.priority
                for action in email_actions
            ) else 0.1
        return super()._score_expectation(expectation, actions)


class MediumGrader(EmailGrader):
    pass


class HardTaskGrader(EmailGrader):
    def score_partial(self, emails: List[Email], actions: List[EmailAction]) -> float:
        base = super().score_partial(emails, actions)
        urgency_order = self._urgency_sequence_score(actions)
        urgent_before_low = self._urgent_before_low_score(actions)
        delegation = self._delegation_score(actions)
        return round(
            self.normalize_score((0.6 * base) + (0.2 * urgency_order) + (0.1 * urgent_before_low) + (0.1 * delegation))

        )

    def final_score(self, actions: List[EmailAction]) -> float:
        return self.score_partial([], actions)

    def _urgency_sequence_score(self, actions: List[EmailAction]) -> float:
        urgent_ids = [
            expectation.email_id
            for expectation in self.expected
            if expectation.priority == EmailPriority.URGENT
        ]
        if not urgent_ids:
            return 0.99

        handled_urgent_ids: list[str] = []
        seen: set[str] = set()
        urgent_lookup = set(urgent_ids)

        for action in actions:
            if action.email_id in urgent_lookup and action.email_id not in seen:
                handled_urgent_ids.append(action.email_id)
                seen.add(action.email_id)

        if not handled_urgent_ids:
            return 0.1

        correctly_sequenced = sum(
            1
            for index, email_id in enumerate(handled_urgent_ids)
            if index < len(urgent_ids) and email_id == urgent_ids[index]
        )
        return self.normalize_score(correctly_sequenced / len(urgent_ids))

    def _urgent_before_low_score(self, actions: List[EmailAction]) -> float:
        action_order = {}
        for index, action in enumerate(actions):
            action_order.setdefault(action.email_id, index)

        urgent_ids = [
            expectation.email_id
            for expectation in self.expected
            if expectation.priority == EmailPriority.URGENT
        ]
        low_ids = [
            expectation.email_id
            for expectation in self.expected
            if expectation.priority == EmailPriority.LOW
        ]

        urgent_positions = [action_order[email_id] for email_id in urgent_ids if email_id in action_order]
        if not urgent_positions:
            return 0.1

        low_positions = [action_order[email_id] for email_id in low_ids if email_id in action_order]
        if not low_positions:
            return self.normalize_score(len(urgent_positions) / len(urgent_ids))

        earliest_low = min(low_positions)
        handled_before_low = sum(1 for position in urgent_positions if position < earliest_low)
        return self.normalize_score(handled_before_low / len(urgent_ids))

    def _delegation_score(self, actions: List[EmailAction]) -> float:
        delegation_expectations = [
            expectation for expectation in self.expected if expectation.final_action == "delegate"
        ]
        if not delegation_expectations:
            return 0.99

        matched = sum(
            1
            for expectation in delegation_expectations
            if self._score_expectation(expectation, actions) >= 0.9
        )
        return self.normalize_score(matched / len(delegation_expectations))


def get_grader(task_name: str, expected_actions: Iterable[ExpectedOutcome]) -> EmailGrader:
    grader_name = task_name.casefold()
    if grader_name == "hard":
        return HardTaskGrader(expected_actions)
    if grader_name == "medium":
        return MediumGrader(expected_actions)
    return EasyGrader(expected_actions)
