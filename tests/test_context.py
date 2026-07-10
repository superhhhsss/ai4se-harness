"""上下文构建器测试."""
import pytest
import tempfile
import os
from ai4se_harness.context import ContextBuilder
from ai4se_harness.config import Config
from ai4se_harness.memory import MemoryStore
from ai4se_harness.models import Action, ActionResult, Feedback
from ai4se_harness.tools.registry import ToolRegistry


@pytest.fixture
def ctx_builder():
    db_path = tempfile.mktemp(suffix=".db")
    memory = MemoryStore(db_path=db_path)
    registry = ToolRegistry()
    registry.register("echo", lambda a: None, {
        "name": "echo", "description": "回显", "parameters": {}
    })
    config = Config.default()
    builder = ContextBuilder(config=config, memory=memory, tools=registry)
    yield builder
    memory.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_build_initial_context(ctx_builder):
    ctx = ctx_builder.build(task="写一个 hello world", history=[], round_count=1)
    assert ctx.messages[0]["role"] == "system"
    assert "写一个 hello world" in ctx.messages[-1]["content"]
    assert len(ctx.tools) >= 1


def test_build_injects_feedback_into_context(ctx_builder):
    history = [
        (Action(tool="write_file", params={"path": "h.py"}),
         ActionResult(success=True, stdout="ok", stderr="", exit_code=0),
         Feedback(passed=False, test_report="1 failed", failed_stage="test",
                  suggestion="修复断言")),
    ]
    ctx = ctx_builder.build(task="修复测试", history=history, round_count=2)
    # Feedback should be in a tool role message
    feedback_messages = [m for m in ctx.messages if m["role"] == "tool" and "修复断言" in m.get("content", "")]
    assert len(feedback_messages) >= 1