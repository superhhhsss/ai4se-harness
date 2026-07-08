"""动作解析器测试."""
import pytest
from ai4se_harness.parser import ActionParser, ParseError


def test_parse_valid_tool_call():
    parser = ActionParser()
    action = parser.parse('{"tool": "write_file", "params": {"path": "a.py", "content": "x=1"}}', round=1)
    assert action.tool == "write_file"
    assert action.params["path"] == "a.py"
    assert action.round == 1


def test_parse_with_markdown_fence():
    parser = ActionParser()
    llm_output = '```json\n{"tool": "read_file", "params": {"path": "test.py"}}\n```'
    action = parser.parse(llm_output, round=2)
    assert action.tool == "read_file"


def test_parse_invalid_json_raises():
    parser = ActionParser()
    with pytest.raises(ParseError):
        parser.parse("not valid json", round=1)


def test_parse_missing_tool_field():
    parser = ActionParser()
    with pytest.raises(ParseError):
        parser.parse('{"params": {}}', round=1)


def test_parse_stop_detection():
    parser = ActionParser()
    action = parser.parse('{"stop": true}', round=3)
    assert action.tool == "stop"