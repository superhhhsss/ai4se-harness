"""文件读写工具."""
import time
from pathlib import Path
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.models import Action, ActionResult


def read_file(action: Action) -> ActionResult:
    t0 = time.monotonic()
    path = Path(action.params["path"])
    try:
        content = path.read_text()
        return ActionResult(success=True, stdout=content, stderr="", exit_code=0,
                           duration_ms=int((time.monotonic() - t0) * 1000))
    except FileNotFoundError:
        return ActionResult(success=False, stdout="", stderr=f"文件不存在: {path}",
                           exit_code=1, duration_ms=int((time.monotonic() - t0) * 1000))


def write_file(action: Action) -> ActionResult:
    t0 = time.monotonic()
    path = Path(action.params["path"])
    content = action.params["content"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return ActionResult(success=True, stdout=f"已写入 {len(content)} 字节到 {path}",
                       stderr="", exit_code=0, files_changed=[str(path)],
                       duration_ms=int((time.monotonic() - t0) * 1000))


def register_file_tools(registry: ToolRegistry) -> None:
    registry.register("read_file", read_file, {
        "name": "read_file", "description": "读取文件内容",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件路径"}},
            "required": ["path"]
        }
    })
    registry.register("write_file", write_file, {
        "name": "write_file", "description": "写入内容到文件",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    })