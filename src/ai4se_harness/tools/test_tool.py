"""测试执行工具."""
import subprocess
import time
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.models import Action, ActionResult


def run_test(action: Action) -> ActionResult:
    t0 = time.monotonic()
    path = action.params.get("path", "tests/")
    try:
        result = subprocess.run(
            ["pytest", path, "-v"], capture_output=True, text=True, timeout=120
        )
        return ActionResult(
            success=result.returncode == 0,
            stdout=result.stdout, stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=int((time.monotonic() - t0) * 1000)
        )
    except FileNotFoundError:
        return ActionResult(success=False, stdout="", stderr="pytest 未安装",
                           exit_code=-1, duration_ms=int((time.monotonic() - t0) * 1000))


def register_test_tool(registry: ToolRegistry) -> None:
    registry.register("run_test", run_test, {
        "name": "run_test", "description": "运行 pytest",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "测试路径 (默认 tests/)"}
            },
            "required": []
        }
    })