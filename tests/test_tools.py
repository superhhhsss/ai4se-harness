"""工具注册表测试."""
import pytest
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.models import Action


def test_register_and_dispatch():
    registry = ToolRegistry()
    registry.register("echo", lambda a: f"echo: {a.params['msg']}",
                      {"name": "echo", "parameters": {"msg": "string"}})
    result = registry.dispatch(Action(tool="echo", params={"msg": "hello"}))
    assert "echo: hello" in str(result)


def test_dispatch_unknown_tool():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="未知工具"):
        registry.dispatch(Action(tool="nonexistent", params={}))


def test_is_registered():
    registry = ToolRegistry()
    registry.register("test", lambda a: None, {})
    assert registry.is_registered("test") is True
    assert registry.is_registered("other") is False


def test_get_tools_schema():
    registry = ToolRegistry()
    registry.register("echo", lambda a: "ok",
                      {"name": "echo", "description": "回显", "parameters": {}})
    schemas = registry.get_tools_schema()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"


def test_all_tools_integration(tmp_path):
    from ai4se_harness.tools.file_tools import register_file_tools
    from ai4se_harness.tools.shell_tool import register_shell_tool
    from ai4se_harness.tools.test_tool import register_test_tool

    registry = ToolRegistry()
    register_file_tools(registry)
    register_shell_tool(registry)
    register_test_tool(registry)

    # 写入 + 读取
    p = tmp_path / "hello.py"
    result = registry.dispatch(Action(tool="write_file", params={"path": str(p), "content": "x=1"}))
    assert result.success is True
    assert "hello.py" in str(result.files_changed)

    result = registry.dispatch(Action(tool="read_file", params={"path": str(p)}))
    assert "x=1" in result.stdout

    # Shell
    result = registry.dispatch(Action(tool="run_shell", params={"command": "echo ok"}))
    assert result.exit_code == 0

    # 4 个工具已注册
    assert len(registry.get_tools_schema()) == 4