"""停机判断测试."""
from ai4se_harness.stop_judge import StopJudge
from ai4se_harness.models import Action, ActionResult, Feedback


def test_stops_on_explicit_stop():
    judge = StopJudge(max_rounds=20)
    reason = judge.check(Action(tool="stop", params={}), feedback=None, round_count=3, history=[])
    assert reason.should_stop is True
    assert reason.reason == "task_completed"


def test_stops_on_max_rounds():
    judge = StopJudge(max_rounds=5)
    reason = judge.check(Action(tool="run_shell", params={}), feedback=None,
                         round_count=5, history=[])
    assert reason.should_stop is True
    assert reason.reason == "max_rounds"


def test_continues_within_rounds():
    judge = StopJudge(max_rounds=20)
    reason = judge.check(Action(tool="write_file", params={}), feedback=None,
                         round_count=3, history=[])
    assert reason.should_stop is False


def test_detects_stuck():
    judge = StopJudge(max_rounds=20)
    history = [
        (Action(tool="write_file", params={"path": "a.py"}, round=i),
         ActionResult(success=True, stdout="", stderr="", exit_code=0),
         Feedback(passed=True))
        for i in range(1, 4)
    ]
    reason = judge.check(action=history[-1][0], feedback=history[-1][2],
                         round_count=3, history=history)
    assert reason.should_stop is True
    assert reason.reason == "stuck"