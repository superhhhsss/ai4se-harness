"""记忆存储测试."""
import pytest
import tempfile
import os
from ai4se_harness.memory import MemoryStore


@pytest.fixture
def memory():
    db_path = tempfile.mktemp(suffix=".db")
    store = MemoryStore(db_path=db_path)
    yield store
    store.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_store_and_retrieve(memory):
    memory.store("python_style", {"convention": "use black formatter", "indent": 4})
    result = memory.retrieve("python")
    assert len(result) > 0
    assert result[0]["key"] == "python_style"


def test_retrieve_empty(memory):
    results = memory.retrieve("nonexistent")
    assert results == []


def test_forget(memory):
    memory.store("temp", {"data": "to delete"})
    memory.forget("temp")
    assert memory.retrieve("temp") == []


def test_list_keys(memory):
    memory.store("a", {"x": 1})
    memory.store("b", {"y": 2})
    keys = memory.list_keys()
    assert "a" in keys
    assert "b" in keys