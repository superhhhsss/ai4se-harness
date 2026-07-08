"""停机条件判断."""
from ai4se_harness.models import Action, Feedback, StopReason


class StopJudge:
    def __init__(self, max_rounds: int = 20, stuck_threshold: int = 3):
        self.max_rounds = max_rounds
        self.stuck_threshold = stuck_threshold

    def check(self, action: Action, feedback: Feedback | None,
              round_count: int, history: list) -> StopReason:
        if action.tool == "stop":
            return StopReason(should_stop=True, reason="task_completed")
        if round_count >= self.max_rounds:
            return StopReason(should_stop=True, reason="max_rounds")
        if self._detect_stuck(history):
            return StopReason(should_stop=True, reason="stuck")
        return StopReason(should_stop=False, reason="")

    def _detect_stuck(self, history: list) -> bool:
        if len(history) < self.stuck_threshold:
            return False
        recent = history[-self.stuck_threshold:]
        first = recent[0][0]
        for a, _, _ in recent[1:]:
            if a.tool != first.tool or a.params != first.params:
                return False
        return True