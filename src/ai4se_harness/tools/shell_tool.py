"""Shell 执行工具."""
import subprocess
import time
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.models import Action, ActionResult


def run_shell(action: Action) -> ActionResult:
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            action.params["command"], shell=True,
            capture_output=True, text=True, timeout=120,
            cwd=action.params.get("cwd", ".")
        )
        return ActionResult(
            success=result.returncode == 0,
            stdout=result.stdout, stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=int((time.monotonic() - t0) * 1000)
        )
    except subprocess.TimeoutExpired:
        return ActionResult(success=False, stdout="", stderr="命令超时 (120s)",
                           exit_code=-1, duration_ms=int((time.monotonic() - t0) * 1000))


def register_shell_tool(registry: ToolRegistry) -> None:
    registry.register("run_shell", run_shell, {
        "name": "run_shell", "description": "执行 shell 命令",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录"}
            },
            "required": ["command"]
        }
    })