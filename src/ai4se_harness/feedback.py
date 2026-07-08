"""反馈收集器 — 确定性质量信号提取（主要贡献）.

核心设计：通过构造注入 test_runner / lint_runner，在生产环境中执行 subprocess
调用 pytest/flake8；在测试中注入返回预设值的 callable。所有分类逻辑为纯函数，
不依赖 LLM 判断。
"""
import re
import subprocess
from typing import Callable
from ai4se_harness.models import Action, ActionResult, Feedback


def _default_test_runner(path: str | None = None):
    target = path or "tests/"
    return subprocess.run(["pytest", target, "-v"], capture_output=True, text=True)


def _default_lint_runner(files: list[str]) -> str:
    try:
        result = subprocess.run(
            ["flake8"] + files + ["--max-line-length=120", "--ignore=E501,W503"],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return ""


def parse_lint_output(output: str) -> list[dict]:
    """解析 flake8 输出为结构化列表."""
    issues = []
    pattern = r"^(.+?):(\d+):(\d+):\s+(.+)$"
    for line in output.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            issues.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "message": match.group(4),
            })
    return issues


class FeedbackCollector:
    def __init__(self, auto_test: bool = True, auto_lint: bool = True,
                 max_self_correct_rounds: int = 3,
                 test_runner: Callable | None = None,
                 lint_runner: Callable | None = None):
        self.auto_test = auto_test
        self.auto_lint = auto_lint
        self.max_self_correct_rounds = max_self_correct_rounds
        self._run_tests = test_runner or _default_test_runner
        self._run_lint = lint_runner or _default_lint_runner
        self.correct_round_count: dict[str, int] = {}

    def collect(self, result: ActionResult, action: Action) -> Feedback:
        if action.tool not in ("write_file", "run_shell"):
            return Feedback(passed=True)

        files = result.files_changed or action.params.get("path", "")
        if isinstance(files, str):
            files = [files]

        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return Feedback(passed=True, test_report="无 Python 文件变更")

        test_failed = False
        lint_failed = False
        test_report = None
        lint_issues = []

        if self.auto_test:
            test_result = self._run_tests()
            if test_result.returncode != 0:
                test_failed = True
                test_report = test_result.stdout + test_result.stderr

        if self.auto_lint:
            lint_output = self._run_lint(py_files)
            if lint_output:
                lint_failed = True
                lint_issues = parse_lint_output(lint_output)

        if test_failed and "SyntaxError" in (test_report or ""):
            failed_stage = "compile"
            suggestion = self._build_suggestion("compile", test_report or "")
        elif test_failed:
            failed_stage = "test"
            suggestion = self._build_suggestion("test", test_report or "")
        elif lint_failed:
            failed_stage = "lint"
            suggestion = self._build_suggestion("lint", "")
        else:
            failed_stage = None
            suggestion = None

        passed = not test_failed and not lint_failed

        task_key = action.params.get("path", "unknown")
        if not passed:
            self.correct_round_count[task_key] = self.correct_round_count.get(task_key, 0) + 1
        else:
            self.correct_round_count.pop(task_key, None)

        return Feedback(
            passed=passed, test_report=test_report,
            lint_issues=lint_issues, failed_stage=failed_stage,
            suggestion=suggestion,
        )

    def is_stuck(self, task_identifier: str) -> bool:
        return self.correct_round_count.get(task_identifier, 0) >= self.max_self_correct_rounds

    def _build_suggestion(self, failed_stage: str, report: str) -> str:
        if failed_stage == "compile":
            return f"语法错误。修复 Python 语法后重试。\n\n{report[:500]}"
        elif failed_stage == "test":
            return f"测试失败。查看 pytest 输出，定位失败断言并修复代码。\n\n{report[:500]}"
        elif failed_stage == "lint":
            return "代码风格问题。修复 lint 错误后重试。"
        return ""