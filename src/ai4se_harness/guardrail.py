"""护栏：在危险动作执行前拦截."""
import re
import os
from pathlib import Path
from ai4se_harness.models import Action, GuardDecision


class Guardrail:
    def __init__(self, patterns: list[str] | None = None, workspace: str | None = None):
        self.patterns = patterns or [
            r"rm\s+(-rf?|--recursive)",
            r"DROP\s+(TABLE|DATABASE)",
            r"sudo\s+",
            r">\s*/dev/",
            r"chmod\s+777",
            r"git\s+push\s+.*(--force|-f)",
        ]
        self.workspace = workspace or os.getcwd()
        self.allowlist: set[str] = set()

    def check(self, action: Action) -> GuardDecision:
        if action.tool == "write_file":
            return self._check_write(action)
        if action.tool in ("read_file", "run_test"):
            return GuardDecision(verdict="ALLOW", reason="安全工具")
        if action.tool == "run_shell":
            return self._check_shell(action)
        return GuardDecision(verdict="ALLOW", reason="未知工具 — 放行")

    def _check_shell(self, action: Action) -> GuardDecision:
        command = action.params.get("command", "")
        if command in self.allowlist:
            return GuardDecision(verdict="ALLOW", reason="在白名单中")
        for pattern in self.patterns:
            if re.search(pattern, command):
                return GuardDecision(
                    verdict="BLOCK",
                    reason=f"匹配危险模式: {pattern}",
                    matched_pattern=pattern,
                )
        return GuardDecision(verdict="ALLOW", reason="安全的 shell 命令")

    def _check_write(self, action: Action) -> GuardDecision:
        path = Path(action.params.get("path", "")).resolve()
        workspace_path = Path(self.workspace).resolve()
        try:
            path.relative_to(workspace_path)
            return GuardDecision(verdict="ALLOW", reason="路径在工作区内")
        except ValueError:
            return GuardDecision(
                verdict="BLOCK",
                reason=f"写入路径超出工作区: {path}",
                matched_pattern="path_escape",
            )