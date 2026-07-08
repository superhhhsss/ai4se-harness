"""Coding Agent Harness 数据模型."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    tool: str
    params: dict[str, Any]
    raw_llm_output: str = ""
    round: int = 0


@dataclass
class ActionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    files_changed: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class Feedback:
    passed: bool
    test_report: str | None = None
    lint_issues: list[dict] = field(default_factory=list)
    failed_stage: str | None = None  # "compile" | "test" | "lint"
    suggestion: str | None = None


@dataclass
class GuardDecision:
    verdict: str  # ALLOW | BLOCK | ASK
    reason: str
    matched_pattern: str | None = None


@dataclass
class StopReason:
    should_stop: bool
    reason: str  # task_completed | max_rounds | user_abort | stuck