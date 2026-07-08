"""LLM 抽象层测试."""
import pytest
from ai4se_harness.llm.base import LLMBackend
from ai4se_harness.llm.mock import MockLLMBackend


def test_mock_returns_preset_responses():
    mock = MockLLMBackend(responses=['{"tool": "read_file", "params": {"path": "x.py"}}'])
    result = mock.chat([{"role": "user", "content": "read x.py"}])
    assert "read_file" in result


def test_mock_raises_when_exhausted():
    mock = MockLLMBackend(responses=["only one"])
    mock.chat([{"role": "user", "content": "hi"}])
    with pytest.raises(IndexError):
        mock.chat([{"role": "user", "content": "again"}])


def test_mock_call_count():
    mock = MockLLMBackend(responses=["a", "b", "c"])
    mock.chat([])
    mock.chat([])
    assert mock.call_count == 2


def test_mock_records_all_calls():
    mock = MockLLMBackend(responses=["r1", "r2"])
    mock.chat([{"role": "user", "content": "msg1"}])
    mock.chat([{"role": "user", "content": "msg2"}])
    assert len(mock.calls) == 2
    assert mock.calls[0][0]["content"] == "msg1"


def test_llm_backend_is_abstract():
    with pytest.raises(TypeError):
        LLMBackend()