"""主循环集成测试 (mock LLM)."""
from ai4se_harness.loop import Harness
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.config import Config


def make_config(**kwargs):
    return Config(
        tools_allowlist=["read_file", "write_file", "run_shell", "run_test"],
        guardrail_patterns=[],
        feedback_auto_test=False,
        feedback_auto_lint=False,
        feedback_max_self_correct_rounds=3,
        loop_max_rounds=kwargs.get("loop_max_rounds", 10),
    )


def test_loop_stops_on_explicit_stop():
    h = Harness(config=make_config(), llm_backend=MockLLMBackend(['{"stop": true}']))
    reason = h.run("say hello")
    assert reason.should_stop is True
    assert reason.reason == "task_completed"


def test_loop_executes_write_and_read(tmp_path):
    p = tmp_path / "test.txt"
    # Use as_posix() to avoid Windows backslash issues in JSON
    path_str = p.as_posix()
    h = Harness(config=make_config(), llm_backend=MockLLMBackend([
        f'{{"tool": "write_file", "params": {{"path": "{path_str}", "content": "hello"}}}}',
        f'{{"tool": "read_file", "params": {{"path": "{path_str}"}}}}',
        '{"stop": true}',
    ]), workspace=str(tmp_path))
    reason = h.run("创建并读取一个文件")
    assert reason.should_stop is True
    assert len(h.history) == 2


def test_loop_stops_at_max_rounds():
    resp = '{"tool": "write_file", "params": {"path": "x.py", "content": "x"}}'
    h = Harness(config=make_config(loop_max_rounds=3),
                llm_backend=MockLLMBackend([resp] * 10))
    reason = h.run("do something")
    assert reason.reason == "max_rounds"


def test_loop_records_history():
    h = Harness(config=make_config(), llm_backend=MockLLMBackend([
        '{"tool": "write_file", "params": {"path": "a.py", "content": "x=1"}}',
        '{"stop": true}',
    ]))
    h.run("write a file")
    assert len(h.history) == 1
    action, result, feedback = h.history[0]
    assert action.tool == "write_file"
    assert result.success is True