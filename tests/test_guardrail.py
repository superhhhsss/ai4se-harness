"""护栏模块测试."""
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.models import Action


def test_blocks_rm_rf():
    g = Guardrail()
    decision = g.check(Action(tool="run_shell", params={"command": "rm -rf /"}))
    assert decision.verdict == "BLOCK"
    assert "rm" in decision.reason.lower()


def test_blocks_drop_table():
    g = Guardrail()
    decision = g.check(Action(tool="run_shell", params={"command": "echo 'DROP TABLE users' | mysql"}))
    assert decision.verdict == "BLOCK"


def test_allows_safe_command():
    g = Guardrail()
    decision = g.check(Action(tool="run_shell", params={"command": "pytest tests/"}))
    assert decision.verdict == "ALLOW"


def test_blocks_write_outside_workspace(tmp_path):
    g = Guardrail(workspace=str(tmp_path))
    decision = g.check(Action(tool="write_file", params={"path": "/etc/passwd", "content": "x"}))
    assert decision.verdict == "BLOCK"


def test_allows_write_inside_workspace(tmp_path):
    g = Guardrail(workspace=str(tmp_path))
    safe_path = str(tmp_path / "a.py")
    decision = g.check(Action(tool="write_file", params={"path": safe_path, "content": "x"}))
    assert decision.verdict == "ALLOW"


def test_allowlist_overrides_block():
    g = Guardrail()
    g.allowlist.add("rm -rf ./build")
    decision = g.check(Action(tool="run_shell", params={"command": "rm -rf ./build"}))
    assert decision.verdict == "ALLOW"


def test_read_and_test_tools_always_allowed():
    g = Guardrail()
    for tool in ["read_file", "run_test"]:
        decision = g.check(Action(tool=tool, params={}))
        assert decision.verdict == "ALLOW"