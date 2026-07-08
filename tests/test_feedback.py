"""反馈收集器测试 — 重点维度."""
import subprocess
from ai4se_harness.feedback import FeedbackCollector, parse_lint_output
from ai4se_harness.models import Action, ActionResult


def make_test_runner(returncode: int, stdout: str, stderr: str):
    def runner(path=None):
        return subprocess.CompletedProcess(args=[], returncode=returncode,
                                           stdout=stdout, stderr=stderr)
    return runner


def make_lint_runner(output: str):
    def runner(files):
        return output
    return runner


# --- 基础收集 ---

def test_collect_test_failure():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "1 failed", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["test_a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "test_a.py"}))
    assert fb.passed is False
    assert fb.failed_stage == "test"
    assert fb.test_report == "1 failed"


def test_collect_lint_issues():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "OK", ""),
        lint_runner=make_lint_runner("a.py:1:1: E302 expected 2 blank lines"),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert fb.passed is False
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_collect_all_pass():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "2 passed", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert fb.passed is True
    assert fb.failed_stage is None


def test_collect_skips_for_read_actions():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAIL", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="content", stderr="", exit_code=0)
    fb = collector.collect(result, Action(tool="read_file", params={"path": "x.py"}))
    assert fb.passed is True


def test_collect_skips_non_python_files():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAIL", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["README.md"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "README.md"}))
    assert fb.passed is True


# --- 失败分类 ---

def test_classify_compile_error():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "", "SyntaxError: invalid syntax"),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["broken.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "broken.py"}))
    assert fb.failed_stage == "compile"
    assert "syntax" in fb.suggestion.lower()


def test_classify_test_failure():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAILED test_x.py::test_foo - assert 1 == 2", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["foo.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "foo.py"}))
    assert fb.failed_stage == "test"
    assert "pytest" in fb.suggestion.lower()


def test_classify_lint_error():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "OK", ""),
        lint_runner=make_lint_runner("x.py:1:1: F401 imported but unused"),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "x.py"}))
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_suggestion_truncates_long_report():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "X" * 1000, ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["big.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "big.py"}))
    assert len(fb.suggestion) < 600


# --- 自修正轮数跟踪 ---

def test_correct_round_tracking():
    collector = FeedbackCollector(max_self_correct_rounds=3)
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    action = Action(tool="write_file", params={"path": "x.py"})

    collector._run_tests = make_test_runner(1, "FAIL", "")
    collector._run_lint = make_lint_runner("")

    for i in range(3):
        fb = collector.collect(result, action)
        assert fb.passed is False
    assert collector.is_stuck("x.py") is True


def test_correct_round_resets_on_pass():
    collector = FeedbackCollector(max_self_correct_rounds=3)
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    action = Action(tool="write_file", params={"path": "x.py"})

    collector._run_tests = make_test_runner(1, "FAIL", "")
    collector._run_lint = make_lint_runner("")
    collector.collect(result, action)

    collector._run_tests = make_test_runner(0, "OK", "")
    collector._run_lint = make_lint_runner("")
    collector.collect(result, action)

    assert collector.is_stuck("x.py") is False


# --- Lint 输出解析 ---

def test_parse_lint_output():
    output = "a.py:1:1: F401 'os' imported but unused\nb.py:5:10: E302 expected 2 blank lines"
    issues = parse_lint_output(output)
    assert len(issues) == 2
    assert issues[0] == {"file": "a.py", "line": 1, "column": 1, "message": "F401 'os' imported but unused"}
    assert issues[1]["file"] == "b.py"