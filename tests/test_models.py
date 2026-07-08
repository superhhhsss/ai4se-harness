"""数据模型测试."""
from ai4se_harness.models import Action, ActionResult, Feedback, GuardDecision, StopReason


def test_action_creation():
    action = Action(tool="write_file", params={"path": "a.py", "content": "x=1"})
    assert action.tool == "write_file"
    assert action.params["path"] == "a.py"


def test_action_result_success():
    result = ActionResult(success=True, stdout="ok", stderr="", exit_code=0,
                          files_changed=["a.py"], duration_ms=150)
    assert result.success is True
    assert result.exit_code == 0


def test_feedback_passed():
    fb = Feedback(passed=True, test_report="2 passed", lint_issues=[], failed_stage=None)
    assert fb.passed is True
    assert fb.lint_issues == []


def test_feedback_failed_with_lint():
    fb = Feedback(passed=False, test_report="",
                  lint_issues=[{"file": "a.py", "line": 1, "message": "E302"}],
                  failed_stage="lint",
                  suggestion="Fix E302: expected 2 blank lines")
    assert fb.passed is False
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_guard_decision_block():
    gd = GuardDecision(verdict="BLOCK", reason="危险: rm -rf /", matched_pattern=r"rm\s+(-rf?)")
    assert gd.verdict == "BLOCK"
    assert gd.matched_pattern is not None


def test_stop_reason_completed():
    sr = StopReason(should_stop=True, reason="task_completed")
    assert sr.should_stop is True