"""机制演示 — 全部在 mock LLM 下确定性运行.

演示 1: 护栏拦截危险命令
演示 2: 注入失败 → 反馈回灌 → agent 修正
演示 3: 反馈分类准确度 (主要贡献)
"""
import subprocess
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.loop import Harness
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.config import Config
from ai4se_harness.models import Action, ActionResult, Feedback


def make_config(**kwargs):
    return Config(
        tools_allowlist=["read_file", "write_file", "run_shell", "run_test"],
        guardrail_patterns=kwargs.get("guardrail_patterns", []),
        feedback_auto_test=False,
        feedback_auto_lint=False,
        feedback_max_self_correct_rounds=3,
        loop_max_rounds=20,
    )


# ====== 演示 1: 护栏拦截 ======

def test_demo1_guardrail_intercepts_dangerous_commands():
    """确定性演示护栏在无真实 LLM 下拦截危险命令."""
    guardrail = Guardrail(patterns=[
        r"rm\s+(-rf?|--recursive)",
        r"DROP\s+(TABLE|DATABASE)",
        r"sudo\s+",
        r">\s*/dev/",
        r"chmod\s+777",
    ])

    # 1a: rm -rf / 被拦截
    action = Action(tool="run_shell", params={"command": "rm -rf / --no-preserve-root"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"
    assert "rm" in decision.reason.lower()

    # 1b: DROP TABLE 被拦截
    action = Action(tool="run_shell", params={"command": "mysql -e 'DROP TABLE users'"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"

    # 1c: 安全命令放行
    action = Action(tool="run_shell", params={"command": "pytest tests/ -v"})
    decision = guardrail.check(action)
    assert decision.verdict == "ALLOW"

    # 1d: 写工作区外被拦截
    guardrail2 = Guardrail(workspace="/tmp/safe")
    action = Action(tool="write_file", params={"path": "/etc/passwd", "content": "x"})
    decision = guardrail2.check(action)
    assert decision.verdict == "BLOCK"


# ====== 演示 2: 失败注入 → 反馈 → 修正 ======

def test_demo2_feedback_drives_self_correction():
    """注入一次测试失败，验证 agent 接收到 feedback 后修正代码."""
    harness = Harness(
        config=make_config(),
        llm_backend=MockLLMBackend(responses=[
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a-b"}}',
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a+b"}}',
            '{"stop": true}',
        ]),
    )

    call_count = [0]

    def staged_collect(result, action):
        call_count[0] += 1
        if call_count[0] == 1:
            return Feedback(
                passed=False,
                test_report="FAILED test_calc.py::test_add - assert -1 == 3",
                failed_stage="test",
                suggestion="测试失败: assert add(1,2) == 3, 但得到 -1。应使用 + 而非 -。",
            )
        return Feedback(passed=True)

    harness.feedback.collect = staged_collect

    reason = harness.run("实现一个 add 函数")

    assert reason.reason == "task_completed"
    assert call_count[0] == 2
    assert harness.history[1][0].params["content"] == "def add(a,b): return a+b"


# ====== 演示 3: 反馈分类准确度 (主要贡献) ======

def test_demo3_feedback_classification():
    """验证反馈收集器正确区分编译错、测试失败和 lint 警告."""
    from ai4se_harness.feedback import parse_lint_output

    def mock_test(rc, stdout, stderr):
        return lambda path=None: subprocess.CompletedProcess(
            args=[], returncode=rc, stdout=stdout, stderr=stderr)

    def mock_lint(output):
        return lambda files: output

    # 场景 A: 语法错 → compile
    collector = FeedbackCollector(
        test_runner=mock_test(1, "", "SyntaxError: invalid syntax"),
        lint_runner=mock_lint(""),
    )
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["bad.py"]),
        Action(tool="write_file", params={"path": "bad.py"})
    )
    assert fb.failed_stage == "compile"
    assert "syntax" in fb.suggestion.lower()

    # 场景 B: 测试失败 → test
    collector._run_tests = mock_test(1, "FAILED test_x.py", "")
    collector._run_lint = mock_lint("")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
        Action(tool="write_file", params={"path": "x.py"})
    )
    assert fb.failed_stage == "test"
    assert "pytest" in fb.suggestion.lower()

    # 场景 C: lint 错误 → lint
    collector._run_tests = mock_test(0, "OK", "")
    collector._run_lint = mock_lint("x.py:1:1: F401 imported but unused")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
        Action(tool="write_file", params={"path": "x.py"})
    )
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1

    # 场景 D: 全部通过 → 无失败
    collector._run_tests = mock_test(0, "3 passed", "")
    collector._run_lint = mock_lint("")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["ok.py"]),
        Action(tool="write_file", params={"path": "ok.py"})
    )
    assert fb.passed is True
    assert fb.failed_stage is None