# Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI coding agent harness with pipeline architecture — context building, LLM calling, action parsing, guardrail with HITL, tool dispatch, feedback collection (main contribution), and stop judgment — all verifiable by mock-LLM deterministic tests.

**Architecture:** 7-stage middleware pipeline (Context → LLM → Parser → Guardrail → Dispatch → Feedback → Stop) with 3 side channels (Memory, Config, Credentials). Each stage is independently testable with mock dependencies.

**Tech Stack:** Python 3.12, openai SDK (DeepSeek), SQLite, keyring, pytest, Click CLI, PyYAML.

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `config.yaml`
- Create: `src/ai4se_harness/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "ai4se-harness"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.0",
    "click>=8.0",
    "pyyaml>=6.0",
    "keyring>=24.0",
]

[project.scripts]
ai4se-harness = "ai4se_harness.cli:main"

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write Makefile**

```makefile
.PHONY: test lint install

install:
	pip install -e .

test:
	pytest tests/ -v

lint:
	flake8 src/ --max-line-length=120

cov:
	pytest tests/ -v --cov=ai4se_harness --cov-report=term

demo:
	pytest tests/test_demo.py -v
```

- [ ] **Step 3: Write config.yaml**

```yaml
model:
  provider: deepseek
  api_base: https://api.deepseek.com
  model: deepseek-chat
  max_tokens: 4096
  temperature: 0.1

tools:
  allowlist: [read_file, write_file, run_shell, run_test]

guardrail:
  dangerous_patterns:
    - "rm\\s+(-rf?|--recursive)"
    - "DROP\\s+(TABLE|DATABASE)"
    - "sudo\\s+"
    - ">\\s*/dev/"
    - "chmod\\s+777"
    - "git\\s+push\\s+.*(--force|-f)"

feedback:
  auto_test: true
  auto_lint: true
  max_self_correct_rounds: 3

loop:
  max_rounds: 20
```

- [ ] **Step 4: Create empty `__init__.py` files**

```bash
echo '"""AI4SE Coding Agent Harness."""' > src/ai4se_harness/__init__.py
echo '"""Tests for AI4SE Harness."""' > tests/__init__.py
```

- [ ] **Step 5: Install and verify**

```bash
pip install -e .
python -c "import ai4se_harness; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml Makefile config.yaml src/ai4se_harness/__init__.py tests/__init__.py
git commit -m "feat: project scaffold with pyproject.toml, Makefile, config.yaml"
```

---

## Task 2: Data Models

**Files:**
- Create: `src/ai4se_harness/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for models**

```python
"""Tests for data models."""
from ai4se_harness.models import Action, ActionResult, Feedback, GuardDecision, StopReason


def test_action_creation():
    action = Action(tool="write_file", params={"path": "a.py", "content": "x=1"})
    assert action.tool == "write_file"
    assert action.params["path"] == "a.py"


def test_action_result_success():
    result = ActionResult(success=True, stdout="ok", stderr="", exit_code=0,
                          files_changed=["a.py"], duration_ms=150)
    assert result.success is True
    assert result.exit_code == 0


def test_feedback_passed():
    fb = Feedback(passed=True, test_report="2 passed", lint_issues=[], failed_stage=None)
    assert fb.passed is True
    assert fb.lint_issues == []


def test_feedback_failed_with_lint():
    fb = Feedback(passed=False, test_report="",
                  lint_issues=[{"file": "a.py", "line": 1, "message": "E302"}],
                  failed_stage="lint",
                  suggestion="Fix E302: expected 2 blank lines")
    assert fb.passed is False
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_guard_decision_block():
    gd = GuardDecision(verdict="BLOCK", reason="Dangerous: rm -rf /", matched_pattern="rm\\s+(-rf?)")
    assert gd.verdict == "BLOCK"
    assert gd.matched_pattern is not None


def test_stop_reason_completed():
    sr = StopReason(should_stop=True, reason="task_completed")
    assert sr.should_stop is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```
Expected: all FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write models.py**

```python
"""Data models for the Coding Agent Harness."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    tool: str
    params: dict[str, Any]
    raw_llm_output: str = ""
    round: int = 0


@dataclass
class ActionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    files_changed: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class Feedback:
    passed: bool
    test_report: str | None = None
    lint_issues: list[dict] = field(default_factory=list)
    failed_stage: str | None = None
    suggestion: str | None = None


@dataclass
class GuardDecision:
    verdict: str  # ALLOW | BLOCK | ASK
    reason: str
    matched_pattern: str | None = None


@dataclass
class StopReason:
    should_stop: bool
    reason: str  # task_completed | max_rounds | user_abort | stuck
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```
Expected: all 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai4se_harness/models.py tests/test_models.py
git commit -m "feat: add data models (Action, ActionResult, Feedback, GuardDecision, StopReason)"
```

---

## Task 3: Config Module

**Files:**
- Create: `src/ai4se_harness/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for config module."""
import tempfile
import os
from ai4se_harness.config import Config


def test_config_loads_from_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
model:
  provider: deepseek
  model: deepseek-chat
  max_tokens: 4096
tools:
  allowlist: [read_file, write_file]
feedback:
  max_self_correct_rounds: 3
""")
        path = f.name
    try:
        cfg = Config.load(path)
        assert cfg.model["provider"] == "deepseek"
        assert cfg.tools_allowlist == ["read_file", "write_file"]
        assert cfg.feedback_max_self_correct_rounds == 3
    finally:
        os.unlink(path)


def test_config_defaults():
    cfg = Config.default()
    assert cfg.model["provider"] == "deepseek"
    assert "read_file" in cfg.tools_allowlist
    assert cfg.loop_max_rounds == 20
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 3: Write config.py**

```python
"""Configuration loader from YAML file."""
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class Config:
    model: dict = field(default_factory=dict)
    tools_allowlist: list[str] = field(default_factory=list)
    guardrail_patterns: list[str] = field(default_factory=list)
    feedback_auto_test: bool = True
    feedback_auto_lint: bool = True
    feedback_max_self_correct_rounds: int = 3
    loop_max_rounds: int = 20

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text())
        return cls(
            model=raw.get("model", {}),
            tools_allowlist=raw.get("tools", {}).get("allowlist", []),
            guardrail_patterns=raw.get("guardrail", {}).get("dangerous_patterns", []),
            feedback_auto_test=raw.get("feedback", {}).get("auto_test", True),
            feedback_auto_lint=raw.get("feedback", {}).get("auto_lint", True),
            feedback_max_self_correct_rounds=raw.get("feedback", {}).get("max_self_correct_rounds", 3),
            loop_max_rounds=raw.get("loop", {}).get("max_rounds", 20),
        )

    @classmethod
    def default(cls) -> "Config":
        return cls.load(Path(__file__).parent.parent.parent / "config.yaml")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ai4se_harness/config.py tests/test_config.py
git commit -m "feat: add config module (YAML loader)"
```

---

## Task 4: Credential Manager

**Files:**
- Create: `src/ai4se_harness/credentials.py`
- Create: `tests/test_credentials.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for credential manager."""
from unittest.mock import patch, MagicMock
from ai4se_harness.credentials import CredentialManager


def test_get_returns_key_from_keyring():
    with patch("keyring.get_password", return_value="sk-test123"):
        cm = CredentialManager(service_name="test-harness")
        assert cm.get() == "sk-test123"


def test_get_returns_none_when_not_set():
    with patch("keyring.get_password", return_value=None):
        cm = CredentialManager(service_name="test-harness")
        assert cm.get() is None


def test_set_stores_key():
    with patch("keyring.set_password") as mock_set:
        cm = CredentialManager(service_name="test-harness")
        cm.set("sk-abc")
        mock_set.assert_called_once_with("test-harness", "api_key", "sk-abc")


def test_clear_deletes_key():
    with patch("keyring.delete_password") as mock_del:
        cm = CredentialManager(service_name="test-harness")
        cm.clear()
        mock_del.assert_called_once_with("test-harness", "api_key")


def test_status_configured():
    with patch("keyring.get_password", return_value="sk-xxx"):
        cm = CredentialManager(service_name="test-harness")
        status = cm.status()
        assert "configured" in status.lower()
        assert "sk-xxx" not in status  # never leaks key


def test_env_fallback():
    with patch("keyring.get_password", return_value=None):
        with patch("os.getenv", return_value="sk-from-env"):
            cm = CredentialManager(service_name="test-harness")
            assert cm.get() == "sk-from-env"
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_credentials.py -v
```

- [ ] **Step 3: Write credentials.py**

```python
"""Credential management using system keyring with env fallback."""
import os
import keyring


class CredentialManager:
    def __init__(self, service_name: str = "ai4se-harness"):
        self.service_name = service_name
        self.username = "api_key"

    def get(self) -> str | None:
        key = keyring.get_password(self.service_name, self.username)
        if key:
            return key
        return os.getenv("DEEPSEEK_API_KEY")

    def set(self, key: str) -> None:
        keyring.set_password(self.service_name, self.username, key)

    def clear(self) -> None:
        try:
            keyring.delete_password(self.service_name, self.username)
        except keyring.errors.PasswordDeleteError:
            pass

    def status(self) -> str:
        if self.get():
            return "API key configured (DeepSeek)"
        return "API key not configured. Run 'ai4se-harness key setup'"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_credentials.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ai4se_harness/credentials.py tests/test_credentials.py
git commit -m "feat: add credential manager (keyring + env fallback)"
```

---

## Task 5: LLM Abstraction Layer

**Files:**
- Create: `src/ai4se_harness/llm/__init__.py`
- Create: `src/ai4se_harness/llm/base.py`
- Create: `src/ai4se_harness/llm/mock.py`
- Create: `src/ai4se_harness/llm/live.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for LLM abstraction layer."""
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


def test_llm_backend_is_abstract():
    with pytest.raises(TypeError):
        LLMBackend()  # cannot instantiate abstract class
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_llm.py -v
```

- [ ] **Step 3: Write llm/__init__.py**

```python
"""LLM abstraction layer."""
from ai4se_harness.llm.base import LLMBackend
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.llm.live import LiveLLMBackend

__all__ = ["LLMBackend", "MockLLMBackend", "LiveLLMBackend"]
```

- [ ] **Step 4: Write llm/base.py**

```python
"""Abstract LLM backend."""
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """Send messages to LLM and return completion text."""
        ...
```

- [ ] **Step 5: Write llm/mock.py**

```python
"""Mock LLM backend for deterministic testing."""
from ai4se_harness.llm.base import LLMBackend


class MockLLMBackend(LLMBackend):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        if self.call_count >= len(self.responses):
            raise IndexError(f"No more mock responses (used {self.call_count}/{len(self.responses)})")
        self.calls.append(messages)
        response = self.responses[self.call_count]
        self.call_count += 1
        return response
```

- [ ] **Step 6: Write llm/live.py**

```python
"""Live LLM backend using OpenAI-compatible API (DeepSeek)."""
from openai import OpenAI
from ai4se_harness.llm.base import LLMBackend


class LiveLLMBackend(LLMBackend):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", max_tokens: int = 4096, temperature: float = 0.1):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
```

- [ ] **Step 7: Run tests to verify pass**

```bash
pytest tests/test_llm.py -v
```

- [ ] **Step 8: Commit**

```bash
git add src/ai4se_harness/llm/ tests/test_llm.py
git commit -m "feat: add LLM abstraction layer (base, mock, live)"
```

---

## Task 6: Memory Store

**Files:**
- Create: `src/ai4se_harness/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for memory store."""
import tempfile
import os
from ai4se_harness.memory import MemoryStore


@pytest.fixture
def memory():
    db_path = tempfile.mktemp(suffix=".db")
    store = MemoryStore(db_path=db_path)
    yield store
    store.close()
    os.unlink(db_path)


def test_store_and_retrieve(memory):
    memory.store("python_style", {"convention": "use black formatter", "indent": 4})
    result = memory.retrieve("python style formatting")
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
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_memory.py -v
```

- [ ] **Step 3: Write memory.py**

```python
"""SQLite-based memory store for cross-session agent memory."""
import json
import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: str = "memory.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def store(self, key: str, value: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO memories (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        self.conn.commit()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT key, value FROM memories WHERE key LIKE ? LIMIT ?",
            (f"%{query}%", top_k)
        )
        results = []
        for row in cursor:
            item = json.loads(row["value"])
            item["key"] = row["key"]
            results.append(item)
        return results

    def forget(self, key: str) -> None:
        self.conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        self.conn.commit()

    def list_keys(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT key FROM memories")]

    def close(self):
        self.conn.close()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_memory.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ai4se_harness/memory.py tests/test_memory.py
git commit -m "feat: add SQLite memory store"
```

---

## Task 7: Action Parser

**Files:**
- Create: `src/ai4se_harness/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for action parser."""
import pytest
from ai4se_harness.parser import ActionParser, ParseError
from ai4se_harness.models import Action


def test_parse_valid_tool_call():
    parser = ActionParser()
    llm_output = '{"tool": "write_file", "params": {"path": "a.py", "content": "x=1"}}'
    action = parser.parse(llm_output, round=1)
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
    with pytest.raises(ParseError) as exc:
        parser.parse("not valid json", round=1)
    assert "not valid json" in str(exc.value)


def test_parse_missing_tool_field():
    parser = ActionParser()
    with pytest.raises(ParseError) as exc:
        parser.parse('{"params": {}}', round=1)
    assert "tool" in str(exc.value)


def test_parse_stop_detection():
    parser = ActionParser()
    action = parser.parse('{"stop": true}', round=3)
    assert action.tool == "stop"
```

- [ ] **Step 2: Run to verify fail, then write parser.py**

```python
"""Parse LLM output into structured Action objects."""
import json
import re
from ai4se_harness.models import Action


class ParseError(Exception):
    """Raised when LLM output cannot be parsed into an Action."""
    pass


class ActionParser:
    def parse(self, llm_output: str, round: int = 0) -> Action:
        raw = llm_output.strip()

        # Strip markdown code fences
        fence_match = re.match(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON from LLM: {raw[:200]}") from e

        if not isinstance(data, dict):
            raise ParseError(f"Expected JSON object, got {type(data).__name__}")

        action = Action(
            tool=data.get("tool", "stop"),
            params=data.get("params", {}),
            raw_llm_output=llm_output,
            round=round,
        )
        return action
```

- [ ] **Step 3: Run tests to verify pass and commit**

```bash
pytest tests/test_parser.py -v
git add src/ai4se_harness/parser.py tests/test_parser.py
git commit -m "feat: add action parser with JSON extraction and validation"
```

---

## Task 8: Tool Registry

**Files:**
- Create: `src/ai4se_harness/tools/__init__.py`
- Create: `src/ai4se_harness/tools/registry.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for registry**

```python
"""Tests for tool registry and built-in tools."""
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
    with pytest.raises(ValueError, match="Unknown tool"):
        registry.dispatch(Action(tool="nonexistent", params={}))


def test_is_registered():
    registry = ToolRegistry()
    registry.register("test", lambda a: None, {})
    assert registry.is_registered("test") is True
    assert registry.is_registered("other") is False


def test_get_tools_schema():
    registry = ToolRegistry()
    registry.register("echo", lambda a: "ok",
                      {"name": "echo", "description": "Echo back", "parameters": {}})
    schemas = registry.get_tools_schema()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"
```

- [ ] **Step 2: Run to verify fail, then write tools/registry.py**

```python
"""Tool registry for agent actions."""
from typing import Any, Callable
from ai4se_harness.models import Action


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[[Action], Any]] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, name: str, func: Callable[[Action], Any], schema: dict) -> None:
        self._tools[name] = func
        self._schemas[name] = schema

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def dispatch(self, action: Action):
        if action.tool not in self._tools:
            raise ValueError(f"Unknown tool: {action.tool}")
        return self._tools[action.tool](action)

    def get_tools_schema(self) -> list[dict]:
        return [
            {"type": "function", "function": schema}
            for schema in self._schemas.values()
        ]
```

- [ ] **Step 3: Write tools/__init__.py**

```python
"""Built-in tools for the Coding Agent Harness."""
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.tools.file_tools import register_file_tools
from ai4se_harness.tools.shell_tool import register_shell_tool
from ai4se_harness.tools.test_tool import register_test_tool

__all__ = ["ToolRegistry", "register_file_tools", "register_shell_tool", "register_test_tool"]
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_tools.py -v
git add src/ai4se_harness/tools/ tests/test_tools.py
git commit -m "feat: add tool registry with registration and dispatch"
```

---

## Task 9: File, Shell, and Test Tools

**Files:**
- Create: `src/ai4se_harness/tools/file_tools.py`
- Create: `src/ai4se_harness/tools/shell_tool.py`
- Create: `src/ai4se_harness/tools/test_tool.py`

- [ ] **Step 1: Write file_tools.py**

```python
"""File I/O tools."""
from pathlib import Path
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.models import Action, ActionResult
import time


def read_file(action: Action) -> ActionResult:
    t0 = time.monotonic()
    path = Path(action.params["path"])
    try:
        content = path.read_text()
        return ActionResult(success=True, stdout=content, stderr="", exit_code=0,
                           files_changed=[], duration_ms=int((time.monotonic() - t0) * 1000))
    except FileNotFoundError:
        return ActionResult(success=False, stdout="", stderr=f"File not found: {path}",
                           exit_code=1, duration_ms=int((time.monotonic() - t0) * 1000))


def write_file(action: Action) -> ActionResult:
    t0 = time.monotonic()
    path = Path(action.params["path"])
    content = action.params["content"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return ActionResult(success=True, stdout=f"Written {len(content)} bytes to {path}",
                       stderr="", exit_code=0, files_changed=[str(path)],
                       duration_ms=int((time.monotonic() - t0) * 1000))


def register_file_tools(registry: ToolRegistry) -> None:
    registry.register("read_file", read_file, {
        "name": "read_file",
        "description": "Read file contents",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path to read"}},
            "required": ["path"]
        }
    })
    registry.register("write_file", write_file, {
        "name": "write_file",
        "description": "Write content to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["path", "content"]
        }
    })
```

- [ ] **Step 2: Write shell_tool.py**

```python
"""Shell execution tool."""
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
        return ActionResult(success=False, stdout="", stderr="Command timed out after 120s",
                           exit_code=-1, duration_ms=int((time.monotonic() - t0) * 1000))


def register_shell_tool(registry: ToolRegistry) -> None:
    registry.register("run_shell", run_shell, {
        "name": "run_shell",
        "description": "Execute a shell command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Working directory"}
            },
            "required": ["command"]
        }
    })
```

- [ ] **Step 3: Write test_tool.py**

```python
"""Test execution tool."""
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
        return ActionResult(success=False, stdout="", stderr="pytest not installed",
                           exit_code=-1, duration_ms=int((time.monotonic() - t0) * 1000))


def register_test_tool(registry: ToolRegistry) -> None:
    registry.register("run_test", run_test, {
        "name": "run_test",
        "description": "Run pytest on the specified path",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Test path (default: tests/)"}
            },
            "required": []
        }
    })
```

- [ ] **Step 4: Add tool integration test to test_tools.py**

```python
def test_file_tools_integration(tmp_path):
    from ai4se_harness.tools.registry import ToolRegistry
    from ai4se_harness.tools.file_tools import register_file_tools
    from ai4se_harness.tools.shell_tool import register_shell_tool
    from ai4se_harness.tools.test_tool import register_test_tool

    registry = ToolRegistry()
    register_file_tools(registry)
    register_shell_tool(registry)
    register_test_tool(registry)

    # File write + read
    p = tmp_path / "hello.py"
    result = registry.dispatch(Action(tool="write_file", params={"path": str(p), "content": "x=1"}))
    assert result.success is True
    assert "hello.py" in str(result.files_changed)

    result = registry.dispatch(Action(tool="read_file", params={"path": str(p)}))
    assert "x=1" in result.stdout

    # Shell
    result = registry.dispatch(Action(tool="run_shell", params={"command": "echo ok"}))
    assert result.exit_code == 0

    # All 4 tools registered
    schemas = registry.get_tools_schema()
    assert len(schemas) == 4
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_tools.py -v
git add src/ai4se_harness/tools/file_tools.py src/ai4se_harness/tools/shell_tool.py src/ai4se_harness/tools/test_tool.py tests/test_tools.py
git commit -m "feat: add built-in tools (file I/O, shell, test runner)"
```

---

## Task 10: Guardrail

**Files:**
- Create: `src/ai4se_harness/guardrail.py`
- Create: `tests/test_guardrail.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for guardrail module."""
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.models import Action, GuardDecision


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


def test_blocks_write_outside_workspace():
    g = Guardrail(workspace="/home/user/project")
    decision = g.check(Action(tool="write_file", params={"path": "/etc/passwd", "content": "x"}))
    assert decision.verdict == "BLOCK"


def test_allows_write_inside_workspace():
    g = Guardrail(workspace="/home/user/project")
    decision = g.check(Action(tool="write_file", params={"path": "/home/user/project/a.py", "content": "x"}))
    assert decision.verdict == "ALLOW"


def test_allowlist_overrides_block():
    g = Guardrail()
    g.allowlist.add("rm -rf ./build")
    decision = g.check(Action(tool="run_shell", params={"command": "rm -rf ./build"}))
    assert decision.verdict == "ALLOW"


def test_file_tools_always_allowed():
    g = Guardrail()
    for tool in ["read_file", "write_file", "run_test"]:
        decision = g.check(Action(tool=tool, params={}))
        assert decision.verdict == "ALLOW"
```

- [ ] **Step 2: Run to verify fail, then write guardrail.py**

```python
"""Guardrail: intercept dangerous actions before execution."""
import re
import os
from pathlib import Path
from ai4se_harness.models import Action, GuardDecision


class Guardrail:
    def __init__(self, patterns: list[str] | None = None, workspace: str | None = None):
        self.patterns = patterns or [
            r"rm\s+(-rf?|--recursive)",
            r"DROP\s+(TABLE|DATABASE)",
            r"sudo\s+",
            r">\s*/dev/",
            r"chmod\s+777",
            r"git\s+push\s+.*(--force|-f)",
        ]
        self.workspace = workspace or os.getcwd()
        self.allowlist: set[str] = set()

    def check(self, action: Action) -> GuardDecision:
        # File tools get path-based checks
        if action.tool == "write_file":
            return self._check_write(action)
        if action.tool in ("read_file", "run_test"):
            return GuardDecision(verdict="ALLOW", reason="Safe tool")

        # Shell commands get pattern-based checks
        if action.tool == "run_shell":
            return self._check_shell(action)

        return GuardDecision(verdict="ALLOW", reason="Unknown tool — allowed")

    def _check_shell(self, action: Action) -> GuardDecision:
        command = action.params.get("command", "")
        if command in self.allowlist:
            return GuardDecision(verdict="ALLOW", reason="In allowlist")
        for pattern in self.patterns:
            if re.search(pattern, command):
                return GuardDecision(
                    verdict="BLOCK",
                    reason=f"Dangerous command pattern matched: {pattern}",
                    matched_pattern=pattern,
                )
        return GuardDecision(verdict="ALLOW", reason="Safe shell command")

    def _check_write(self, action: Action) -> GuardDecision:
        path = Path(action.params.get("path", "")).resolve()
        workspace_path = Path(self.workspace).resolve()
        try:
            path.relative_to(workspace_path)
            return GuardDecision(verdict="ALLOW", reason="Path within workspace")
        except ValueError:
            return GuardDecision(
                verdict="BLOCK",
                reason=f"Write path outside workspace: {path}",
                matched_pattern="path_escape",
            )
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_guardrail.py -v
git add src/ai4se_harness/guardrail.py tests/test_guardrail.py
git commit -m "feat: add guardrail with regex pattern matching and workspace boundary"
```

---

## Task 11: Feedback Collector (Deep Dimension)

**Files:**
- Create: `src/ai4se_harness/feedback.py`
- Create: `tests/test_feedback.py`

This is the main contribution — more tests and richer logic.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for feedback collector."""
import tempfile
import os
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.models import Action, ActionResult, Feedback


def test_collect_test_failure_detected():
    collector = FeedbackCollector()
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["test_a.py"])
    # Mock _run_tests to return failure
    collector._run_tests = lambda path=None: subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 failed", stderr="")
    collector._run_lint = lambda files: ""
    feedback = collector.collect(result, Action(tool="write_file", params={"path": "test_a.py"}))
    assert feedback.passed is False
    assert feedback.failed_stage == "test"
    assert feedback.test_report == "1 failed"


def test_collect_lint_issues():
    collector = FeedbackCollector()
    collector._run_tests = lambda path=None: subprocess.CompletedProcess(
        args=[], returncode=0, stdout="all passed", stderr="")
    collector._run_lint = lambda files: "a.py:1:1: E302 expected 2 blank lines"
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    feedback = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert feedback.passed is False
    assert feedback.failed_stage == "lint"
    assert len(feedback.lint_issues) == 1


def test_collect_all_pass():
    collector = FeedbackCollector()
    collector._run_tests = lambda path=None: subprocess.CompletedProcess(
        args=[], returncode=0, stdout="2 passed", stderr="")
    collector._run_lint = lambda files: ""
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    feedback = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert feedback.passed is True
    assert feedback.failed_stage is None


def test_collect_skips_for_read_actions():
    collector = FeedbackCollector()
    result = ActionResult(success=True, stdout="content", stderr="", exit_code=0)
    feedback = collector.collect(result, Action(tool="read_file", params={"path": "x.py"}))
    assert feedback.passed is True


def test_collect_compile_error():
    collector = FeedbackCollector()
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["broken.py"])
    collector._run_tests = lambda path=None: subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="SyntaxError: invalid syntax")
    collector._run_lint = lambda files: ""
    feedback = collector.collect(result, Action(tool="write_file", params={"path": "broken.py"}))
    assert feedback.passed is False
    assert feedback.failed_stage == "compile"
    assert "syntaxerror" in feedback.suggestion.lower()


def test_suggestion_for_test_failure_mentions_pytest():
    collector = FeedbackCollector()
    collector._run_tests = lambda path=None: subprocess.CompletedProcess(
        args=[], returncode=1, stdout="FAILED test_foo.py::test_bar - assert 1 == 2", stderr="")
    collector._run_lint = lambda files: ""
    feedback = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["foo.py"]),
        Action(tool="write_file", params={"path": "foo.py"})
    )
    assert "pytest" in feedback.suggestion.lower() or "test failure" in feedback.suggestion.lower()


def test_collect_no_test_triggers_for_pure_shell():
    collector = FeedbackCollector()
    feedback = collector.collect(
        ActionResult(success=True, stdout="ok", stderr="", exit_code=0),
        Action(tool="run_shell", params={"command": "echo hello"})
    )
    assert feedback.passed is True
```

- [ ] **Step 2: Run to verify fail, then write feedback.py**

```python
"""Feedback Collector — deterministic quality signal extraction (main contribution).

The core insight: coding agents have access to objective, deterministic feedback
signals (test results, linter output, compiler errors). This module captures them
and structures the information for injection back into the agent loop.
"""
import re
import subprocess
from ai4se_harness.models import Action, ActionResult, Feedback


class FeedbackCollector:
    """Collects and classifies feedback from tool execution results."""

    def __init__(self, auto_test: bool = True, auto_lint: bool = True,
                 max_self_correct_rounds: int = 3):
        self.auto_test = auto_test
        self.auto_lint = auto_lint
        self.max_self_correct_rounds = max_self_correct_rounds
        self.correct_round_count: dict[str, int] = {}

    def collect(self, result: ActionResult, action: Action) -> Feedback:
        if action.tool not in ("write_file", "run_shell"):
            return Feedback(passed=True)

        files = result.files_changed or action.params.get("path", "")
        if isinstance(files, str):
            files = [files]

        # Only run tests/lint for Python files
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return Feedback(passed=True, test_report="No Python files changed")

        test_failed = False
        lint_failed = False
        test_report = None
        lint_issues = []

        if self.auto_test:
            test_result = self._run_tests()
            if test_result.returncode != 0:
                test_failed = True
                test_report = test_result.stdout + test_result.stderr

        if self.auto_lint:
            lint_output = self._run_lint(py_files)
            if lint_output:
                lint_failed = True
                lint_issues = self._parse_lint(lint_output)

        if test_failed and "SyntaxError" in (test_report or ""):
            failed_stage = "compile"
            suggestion = self._build_suggestion("compile", test_report or "")
        elif test_failed:
            failed_stage = "test"
            suggestion = self._build_suggestion("test", test_report or "")
        elif lint_failed:
            failed_stage = "lint"
            suggestion = self._build_suggestion("lint", "")
        else:
            failed_stage = None
            suggestion = None

        passed = not test_failed and not lint_failed
        task_key = action.params.get("path", "unknown")
        if not passed:
            self.correct_round_count[task_key] = self.correct_round_count.get(task_key, 0) + 1
        else:
            self.correct_round_count.pop(task_key, None)

        return Feedback(
            passed=passed,
            test_report=test_report,
            lint_issues=lint_issues,
            failed_stage=failed_stage,
            suggestion=suggestion,
        )

    def is_stuck(self, task_identifier: str) -> bool:
        return self.correct_round_count.get(task_identifier, 0) >= self.max_self_correct_rounds

    def _run_tests(self, path: str | None = None):
        target = path or "tests/"
        return subprocess.run(["pytest", target, "-v"], capture_output=True, text=True)

    def _run_lint(self, files: list[str]) -> str:
        try:
            result = subprocess.run(
                ["flake8"] + files + ["--max-line-length=120", "--ignore=E501,W503"],
                capture_output=True, text=True
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return ""

    def _parse_lint(self, output: str) -> list[dict]:
        issues = []
        pattern = r"^(.+?):(\d+):(\d+):\s+(.+)$"
        for line in output.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                issues.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "message": match.group(4),
                })
        return issues

    def _build_suggestion(self, failed_stage: str, report: str) -> str:
        if failed_stage == "compile":
            return f"Syntax error detected. Fix the Python syntax and re-run.\n\n{report[:500]}"
        elif failed_stage == "test":
            return f"Test failure detected. Review the pytest output, identify the failing assertion, and fix the code.\n\n{report[:500]}"
        elif failed_stage == "lint":
            return "Lint issues found. Fix code style issues and re-run."
        return ""
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_feedback.py -v
git add src/ai4se_harness/feedback.py tests/test_feedback.py
git commit -m "feat: add feedback collector with failure classification (main contribution)"
```

---

## Task 12: Stop Judge

**Files:**
- Create: `src/ai4se_harness/stop_judge.py`
- Create: `tests/test_stop_judge.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for stop judge."""
from ai4se_harness.stop_judge import StopJudge
from ai4se_harness.models import Action, ActionResult, Feedback, StopReason


def test_stops_on_explicit_stop():
    judge = StopJudge(max_rounds=20)
    action = Action(tool="stop", params={})
    reason = judge.check(action=action, feedback=None, round_count=3, history=[])
    assert reason.should_stop is True
    assert reason.reason == "task_completed"


def test_stops_on_max_rounds():
    judge = StopJudge(max_rounds=5)
    reason = judge.check(action=Action(tool="run_shell", params={}), feedback=None,
                         round_count=5, history=[])
    assert reason.should_stop is True
    assert reason.reason == "max_rounds"


def test_continues_within_rounds():
    judge = StopJudge(max_rounds=20)
    reason = judge.check(action=Action(tool="write_file", params={}), feedback=None,
                         round_count=3, history=[])
    assert reason.should_stop is False


def test_detects_stuck():
    judge = StopJudge(max_rounds=20)
    history = [
        (Action(tool="write_file", params={"path": "a.py"}, round=1),
         ActionResult(success=True, stdout="", stderr="", exit_code=0),
         Feedback(passed=True)),
        (Action(tool="write_file", params={"path": "a.py"}, round=2),
         ActionResult(success=True, stdout="", stderr="", exit_code=0),
         Feedback(passed=True)),
        (Action(tool="write_file", params={"path": "a.py"}, round=3),
         ActionResult(success=True, stdout="", stderr="", exit_code=0),
         Feedback(passed=True)),
    ]
    reason = judge.check(action=history[-1][0], feedback=history[-1][2],
                         round_count=3, history=history)
    assert reason.should_stop is True
    assert reason.reason == "stuck"
```

- [ ] **Step 2: Run to verify fail, then write stop_judge.py**

```python
"""Stop conditions for the agent loop."""
from ai4se_harness.models import Action, Feedback, StopReason


class StopJudge:
    def __init__(self, max_rounds: int = 20, stuck_threshold: int = 3):
        self.max_rounds = max_rounds
        self.stuck_threshold = stuck_threshold

    def check(self, action: Action, feedback: Feedback | None,
              round_count: int, history: list) -> StopReason:
        if action.tool == "stop":
            return StopReason(should_stop=True, reason="task_completed")

        if round_count >= self.max_rounds:
            return StopReason(should_stop=True, reason="max_rounds")

        if feedback is not None and not feedback.passed:
            if self._detect_stuck(history):
                return StopReason(should_stop=True, reason="stuck")

        return StopReason(should_stop=False, reason="")

    def _detect_stuck(self, history: list) -> bool:
        if len(history) < self.stuck_threshold:
            return False
        recent = history[-self.stuck_threshold:]
        first_action = recent[0][0]
        for a, _, _ in recent[1:]:
            if a.tool != first_action.tool or a.params != first_action.params:
                return False
        return True
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_stop_judge.py -v
git add src/ai4se_harness/stop_judge.py tests/test_stop_judge.py
git commit -m "feat: add stop judge (task complete, max rounds, stuck detection)"
```

---

## Task 13: Context Builder

**Files:**
- Create: `src/ai4se_harness/context.py`
- Create: `tests/test_context.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for context builder."""
from ai4se_harness.context import ContextBuilder
from ai4se_harness.config import Config
from ai4se_harness.memory import MemoryStore
from ai4se_harness.models import Action, ActionResult, Feedback
from ai4se_harness.tools.registry import ToolRegistry
import tempfile
import os


@pytest.fixture
def ctx_builder():
    db_path = tempfile.mktemp(suffix=".db")
    memory = MemoryStore(db_path=db_path)
    registry = ToolRegistry()
    registry.register("echo", lambda a: None, {"name": "echo", "description": "Echo", "parameters": {}})
    config = Config.default()
    builder = ContextBuilder(config=config, memory=memory, tools=registry)
    yield builder
    memory.close()
    os.unlink(db_path)


def test_build_initial_context(ctx_builder):
    ctx = ctx_builder.build(task="write a hello world function", history=[], round_count=1)
    assert ctx.messages[0]["role"] == "system"
    assert "write a hello world function" in ctx.messages[-1]["content"]
    assert len(ctx.tools) >= 1


def test_build_with_history(ctx_builder):
    history = [
        (Action(tool="write_file", params={"path": "h.py"}),
         ActionResult(success=True, stdout="ok", stderr="", exit_code=0),
         Feedback(passed=False, test_report="1 failed", failed_stage="test",
                  suggestion="Fix the assertion")),
    ]
    ctx = ctx_builder.build(task="fix tests", history=history, round_count=2)
    content = ctx.messages[-1]["content"]
    assert "feedback" in content.lower() or "failed" in content.lower()
```

- [ ] **Step 2: Run to verify fail, then write context.py**

```python
"""Context Builder: assemble prompt context from config, memory, and history."""
from dataclasses import dataclass
from ai4se_harness.config import Config
from ai4se_harness.memory import MemoryStore
from ai4se_harness.tools.registry import ToolRegistry


@dataclass
class Context:
    messages: list[dict]
    tools: list[dict] | None


SYSTEM_PROMPT = """You are a coding agent. You have access to tools for reading/writing files,
running shell commands, and executing tests. For each step, output a JSON object:

{"tool": "<tool_name>", "params": {...}}
or {"stop": true} when the task is complete.

Always respond with valid JSON only. No explanations outside the JSON."""


class ContextBuilder:
    def __init__(self, config: Config, memory: MemoryStore, tools: ToolRegistry):
        self.config = config
        self.memory = memory
        self.tools = tools

    def build(self, task: str, history: list, round_count: int) -> Context:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject relevant memories
        memories = self.memory.retrieve(task)
        if memories:
            mem_text = "Relevant context from past sessions:\n"
            for m in memories:
                mem_text += f"- {m}\n"
            messages.append({"role": "system", "content": mem_text})

        # Inject conversation history
        for action, result, feedback in history:
            messages.append({
                "role": "assistant",
                "content": f'{{"tool": "{action.tool}", "params": {action.params}}}'
            })
            fb_text = f"Result: {'PASS' if result.success else 'FAIL'}\n{result.stdout[:1000]}"
            if feedback and not feedback.passed:
                fb_text += f"\nFeedback: {feedback.suggestion or feedback.failed_stage}"
            messages.append({"role": "user", "content": fb_text})

        # Current task
        messages.append({
            "role": "user",
            "content": f"Task: {task}\n\nProduce the next action as JSON."
        })

        return Context(
            messages=messages,
            tools=self.tools.get_tools_schema() if self.tools.get_tools_schema() else None,
        )
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_context.py -v
git add src/ai4se_harness/context.py tests/test_context.py
git commit -m "feat: add context builder with memory injection and history assembly"
```

---

## Task 14: Main Loop

**Files:**
- Create: `src/ai4se_harness/loop.py`
- Create: `tests/test_loop.py`

- [ ] **Step 1: Write failing test for main loop with mock LLM**

```python
"""Tests for main loop (integration tests with mock LLM)."""
from ai4se_harness.loop import Harness
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.config import Config
from ai4se_harness.models import StopReason


def make_harness(mock_responses: list[str]) -> Harness:
    config = Config(
        tools_allowlist=["read_file", "write_file", "run_shell", "run_test"],
        guardrail_patterns=[],
        feedback_auto_test=False,
        feedback_auto_lint=False,
        loop_max_rounds=10,
    )
    return Harness(config=config, llm_backend=MockLLMBackend(responses=mock_responses))


def test_loop_stops_on_explicit_stop():
    h = make_harness(['{"stop": true}'])
    reason = h.run("say hello")
    assert reason.should_stop is True
    assert reason.reason == "task_completed"


def test_loop_executes_write_and_read():
    h = make_harness([
        '{"tool": "write_file", "params": {"path": "/tmp/test.txt", "content": "hello"}}',
        '{"tool": "read_file", "params": {"path": "/tmp/test.txt"}}',
        '{"stop": true}',
    ])
    reason = h.run("create and read a file")
    assert reason.should_stop is True
    assert len(h.history) == 2


def test_loop_stops_at_max_rounds():
    h = make_harness(['{"tool": "write_file", "params": {"path": "x.py", "content": "x"}}'] * 10)
    h.config.loop_max_rounds = 3
    reason = h.run("do something")
    assert reason.reason == "max_rounds"
```

- [ ] **Step 2: Run to verify fail, then write loop.py**

```python
"""Main agent loop orchestrator — the heart of the harness."""
from ai4se_harness.llm.base import LLMBackend
from ai4se_harness.config import Config
from ai4se_harness.context import ContextBuilder
from ai4se_harness.parser import ActionParser
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.tools import register_file_tools, register_shell_tool, register_test_tool
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.stop_judge import StopJudge
from ai4se_harness.memory import MemoryStore
from ai4se_harness.models import StopReason


class Harness:
    def __init__(self, config: Config, llm_backend: LLMBackend,
                 memory: MemoryStore | None = None):
        self.config = config
        self.llm = llm_backend
        self.memory = memory or MemoryStore()

        self.tools = ToolRegistry()
        register_file_tools(self.tools)
        register_shell_tool(self.tools)
        register_test_tool(self.tools)

        self.parser = ActionParser()
        self.guardrail = Guardrail(patterns=config.guardrail_patterns)
        self.feedback = FeedbackCollector(
            auto_test=config.feedback_auto_test,
            auto_lint=config.feedback_auto_lint,
            max_self_correct_rounds=config.feedback_max_self_correct_rounds,
        )
        self.stop_judge = StopJudge(max_rounds=config.loop_max_rounds)
        self.context_builder = ContextBuilder(
            config=config, memory=self.memory, tools=self.tools
        )
        self.history: list = []

    def run(self, task: str) -> StopReason:
        self.history = []
        round_count = 0

        while True:
            round_count += 1
            ctx = self.context_builder.build(task, self.history, round_count)

            # LLM call
            response = self.llm.chat(ctx.messages, ctx.tools)

            # Parse
            action = self.parser.parse(response, round=round_count)

            # Stop check (LLM said "stop")
            if action.tool == "stop":
                reason = self.stop_judge.check(action, None, round_count, self.history)
                if reason.should_stop:
                    return reason

            # Guardrail
            decision = self.guardrail.check(action)
            if decision.verdict == "BLOCK":
                if not self._handle_block(action, decision):
                    return StopReason(should_stop=True, reason="user_abort")

            # Dispatch
            result = self.tools.dispatch(action)

            # Feedback
            feedback = self.feedback.collect(result, action)

            self.history.append((action, result, feedback))

            # Stop check
            reason = self.stop_judge.check(action, feedback, round_count, self.history)
            if reason.should_stop:
                return reason

    def _handle_block(self, action, decision) -> bool:
        """HITL: ask user to confirm/override/reject blocked action."""
        print(f"\n[GUARDRAIL] BLOCKED: {decision.reason}")
        print(f"  Action: {action.tool}({action.params})")
        while True:
            choice = input("  [C]onfirm / [R]eject / [M]odify: ").strip().lower()
            if choice == "c":
                self.guardrail.allowlist.add(action.params.get("command", ""))
                return True
            elif choice == "r":
                return False
            elif choice == "m":
                new_cmd = input("  New command: ")
                action.params["command"] = new_cmd
                return self.guardrail.check(action).verdict != "BLOCK" or self._handle_block(action, self.guardrail.check(action))
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_loop.py -v
git add src/ai4se_harness/loop.py tests/test_loop.py
git commit -m "feat: add main loop orchestrator (all 7 pipeline stages wired)"
```

---

## Task 15: CLI Entry Point

**Files:**
- Create: `src/ai4se_harness/cli.py`

- [ ] **Step 1: Write cli.py**

```python
"""CLI entry point for the Coding Agent Harness."""
import click
from ai4se_harness.config import Config
from ai4se_harness.llm.live import LiveLLMBackend
from ai4se_harness.credentials import CredentialManager
from ai4se_harness.loop import Harness


@click.group()
def main():
    """AI4SE Coding Agent Harness — LLM-driven coding with guardrails and feedback."""
    pass


@main.command()
def run():
    """Start the interactive coding agent."""
    creds = CredentialManager()
    api_key = creds.get()
    if not api_key:
        click.echo("No API key configured. Run 'ai4se-harness key setup' first.")
        raise SystemExit(3)

    config = Config.default()
    llm = LiveLLMBackend(
        api_key=api_key,
        base_url=config.model.get("api_base", "https://api.deepseek.com"),
        model=config.model.get("model", "deepseek-chat"),
    )
    harness = Harness(config=config, llm_backend=llm)

    click.echo("AI4SE Coding Agent Harness ready. Type your task (or 'quit' to exit).")
    while True:
        task = click.prompt("\nTask", prompt_suffix="> ").strip()
        if task.lower() in ("quit", "exit", "q"):
            break
        reason = harness.run(task)
        click.echo(f"\nStopped: {reason.reason}")


@main.group()
def key():
    """Manage API key."""
    pass


@key.command("setup")
def key_setup():
    """Securely store your API key."""
    creds = CredentialManager()
    import getpass
    api_key = getpass.getpass("Enter your DeepSeek API key: ")
    creds.set(api_key)
    click.echo("Key saved.")


@key.command("status")
def key_status():
    """Show API key status."""
    creds = CredentialManager()
    click.echo(creds.status())


@key.command("clear")
def key_clear():
    """Remove stored API key."""
    creds = CredentialManager()
    creds.clear()
    click.echo("Key removed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI loads**

```bash
pip install -e .
python -m ai4se_harness.cli --help
```
Expected: Show command groups (run, key)

- [ ] **Step 3: Commit**

```bash
git add src/ai4se_harness/cli.py
git commit -m "feat: add CLI entry point (click-based)"
```

---

## Task 16: Mechanism Demo

**Files:**
- Create: `tests/test_demo.py`

- [ ] **Step 1: Write three demo tests**

```python
"""Mechanism demonstrations — mock LLM deterministic verification.

Demo 1: Guardrail intercepts dangerous action
Demo 2: Failure injection → feedback → agent self-corrects
Demo 3: Feedback classification accuracy (main contribution)
"""
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.loop import Harness
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.config import Config
from ai4se_harness.models import Action, ActionResult, Feedback
from ai4se_harness.parser import ActionParser


def make_config(**kwargs):
    return Config(
        tools_allowlist=["read_file", "write_file", "run_shell", "run_test"],
        guardrail_patterns=kwargs.get("guardrail_patterns", []),
        feedback_auto_test=False,
        feedback_auto_lint=False,
        feedback_max_self_correct_rounds=3,
        loop_max_rounds=20,
    )


# === Demo 1: Guardrail intercepts dangerous command ===

def test_demo1_guardrail_blocks_rm_rf():
    """Demonstrate deterministic guardrail interception without real LLM."""
    guardrail = Guardrail(patterns=[
        r"rm\s+(-rf?|--recursive)",
        r"DROP\s+(TABLE|DATABASE)",
        r"sudo\s+",
        r">\s*/dev/",
        r"chmod\s+777",
    ])

    # Test 1a: rm -rf / is blocked
    action = Action(tool="run_shell", params={"command": "rm -rf / --no-preserve-root"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"
    assert "rm" in decision.reason.lower()

    # Test 1b: DROP TABLE is blocked
    action = Action(tool="run_shell", params={"command": "mysql -e 'DROP TABLE users'"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"

    # Test 1c: safe command is allowed
    action = Action(tool="run_shell", params={"command": "pytest tests/ -v"})
    decision = guardrail.check(action)
    assert decision.verdict == "ALLOW"

    # Test 1d: writing outside workspace is blocked
    guardrail2 = Guardrail(workspace="/tmp/safe")
    action = Action(tool="write_file", params={"path": "/etc/passwd", "content": "x"})
    decision = guardrail2.check(action)
    assert decision.verdict == "BLOCK"


# === Demo 2: Failure injection → feedback → self-correction ===

def test_demo2_feedback_drives_self_correction():
    """Inject a test failure, verify agent receives feedback and corrects code."""
    harness = Harness(
        config=make_config(),
        llm_backend=MockLLMBackend(responses=[
            # Round 1: Write buggy code
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a-b"}}',
            # Round 2: After receiving feedback about test failure, fix the code
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a+b"}}',
            # Round 3: Stop
            '{"stop": true}',
        ]),
    )

    # Inject feedback collector that will report failure on round 1
    original_collect = harness.feedback.collect
    call_count = [0]

    def staged_collect(result, action):
        call_count[0] += 1
        if call_count[0] == 1:
            return Feedback(
                passed=False,
                test_report="FAILED test_calc.py::test_add - assert -1 == 3",
                failed_stage="test",
                suggestion="Test failure: assert add(1,2) == 3, but got -1. Fix: use + instead of -.",
            )
        return Feedback(passed=True)

    harness.feedback.collect = staged_collect

    reason = harness.run("write an add function")

    # It should have completed (not stuck, not max_rounds)
    assert reason.reason == "task_completed"
    assert call_count[0] == 2  # two write actions triggered feedback
    # The second write should have the corrected version
    assert harness.history[1][0].params["content"] == "def add(a,b): return a+b"


# === Demo 3: Feedback classification accuracy (main contribution) ===

def test_demo3_feedback_classifies_failure_types():
    """Verify feedback collector correctly classifies compile, test, and lint failures."""
    collector = FeedbackCollector(auto_test=True, auto_lint=True)

    # Mock subprocess results
    import subprocess
    original_run = collector._run_tests
    original_lint = collector._run_lint

    try:
        # Case A: Syntax error → classified as "compile"
        collector._run_tests = lambda path=None: type("R", (), {"returncode": 1, "stdout": "", "stderr": "SyntaxError: invalid syntax"})()
        collector._run_lint = lambda files: ""
        fb = collector.collect(
            ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["bad.py"]),
            Action(tool="write_file", params={"path": "bad.py"})
        )
        assert fb.failed_stage == "compile"
        assert "syntax" in fb.suggestion.lower()

        # Case B: Test failure → classified as "test"
        collector._run_tests = lambda path=None: type("R", (), {"returncode": 1, "stdout": "FAILED test_x.py", "stderr": ""})()
        collector._run_lint = lambda files: ""
        fb = collector.collect(
            ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
            Action(tool="write_file", params={"path": "x.py"})
        )
        assert fb.failed_stage == "test"
        assert "pytest" in fb.suggestion.lower()

        # Case C: Lint error → classified as "lint"
        collector._run_tests = lambda path=None: type("R", (), {"returncode": 0, "stdout": "OK", "stderr": ""})()
        collector._run_lint = lambda files: "x.py:1:1: F401 imported but unused"
        fb = collector.collect(
            ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
            Action(tool="write_file", params={"path": "x.py"})
        )
        assert fb.failed_stage == "lint"
        assert len(fb.lint_issues) == 1

        # Case D: All pass → no failure
        collector._run_tests = lambda path=None: type("R", (), {"returncode": 0, "stdout": "3 passed", "stderr": ""})()
        collector._run_lint = lambda files: ""
        fb = collector.collect(
            ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["ok.py"]),
            Action(tool="write_file", params={"path": "ok.py"})
        )
        assert fb.passed is True
        assert fb.failed_stage is None
    finally:
        collector._run_tests = original_run
        collector._run_lint = original_lint
```

- [ ] **Step 2: Run demo tests**

```bash
pytest tests/test_demo.py -v
```
Expected: all 3 demo tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_demo.py
git commit -m "feat: add mechanism demo tests (guardrail, self-correction, classification)"
```

---

## Task 17: Docker + CI

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

ENTRYPOINT ["ai4se-harness"]
```

- [ ] **Step 2: Write CI config**

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: make test

  build-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t ai4se-harness .
```

- [ ] **Step 3: Update pyproject.toml with dev dependencies**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "flake8>=7.0",
]
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .github/workflows/ci.yml pyproject.toml
git commit -m "feat: add Dockerfile and CI (unit-test + docker build)"
```

---

## Task 18: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# AI4SE Coding Agent Harness

A CLI coding agent harness with pipeline architecture, built for the AI4SE final project.
Agent = LLM + Harness. All mechanisms are code, not prompts.

## Quick Start

```bash
pip install ai4se-harness
ai4se-harness key setup    # securely store your DeepSeek API key
ai4se-harness run          # start the agent
```

### Docker

```bash
docker pull ghcr.io/superhhhsss/ai4se-harness:latest
docker run -it -e DEEPSEEK_API_KEY=sk-xxx ai4se-harness run
```

## Key Management

API keys are stored in your system keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service).
Never hardcoded, never committed.

Commands:
- `ai4se-harness key setup` — store your key securely
- `ai4se-harness key status` — check if key is configured
- `ai4se-harness key clear` — remove stored key

Environment variable fallback: `DEEPSEEK_API_KEY` (not recommended — plaintext).

## Architecture

7-stage pipeline: Context Builder → LLM Call → Action Parser → Guardrail (HITL) → Tool Dispatch → Feedback Collector → Stop Judge

3 side channels: Memory (SQLite), Config (YAML), Credentials (keyring)

Main contribution: Feedback Collector — deterministic test/lint result parsing with failure classification (compile vs test vs lint).

## Development

```bash
make install    # pip install -e .
make test       # run all tests
make lint       # flake8
make cov        # coverage report
make demo       # mechanism demo tests
```

## Directory Structure

```
src/ai4se_harness/    — harness source
tests/               — test suite (mock LLM, deterministic)
config.yaml          — default configuration
```

## Known Limitations

- Only supports Python project testing (pytest/flake8)
- Single LLM backend (DeepSeek); add providers by implementing LLMBackend
- No streaming responses
- File safety: write operations restricted to workspace directory

## Security

- API key: system keyring (primary) or env var (fallback)
- Shell: regex-based dangerous command detection
- File IO: workspace boundary enforcement
- No credentials in git history or logs
```

- [ ] **Step 2: Commit and push**

```bash
git add README.md
git commit -m "docs: add README with install, architecture, and security docs"
git push
```

---

## Dependency Graph

```
Task 1 (scaffold)
  ├── Task 2 (models)
  │     ├── Task 3 (config) ──┐
  │     ├── Task 4 (credentials)
  │     ├── Task 5 (LLM) ─────┤
  │     ├── Task 6 (memory) ──┤
  │     ├── Task 7 (parser) ──┤
  │     ├── Task 8 (tools registry)
  │     │     └── Task 9 (file/shell/test tools)
  │     ├── Task 10 (guardrail)
  │     ├── Task 12 (stop judge)
  │     └── Task 11 (feedback) ──┐
  │                              │
  └──────────────────────────────┼── Task 13 (context builder)
                                 │         │
                                 │    Task 14 (main loop)
                                 │         │
                                 │    Task 15 (CLI)
                                 │         │
                                 │    Task 16 (demo tests)
                                 │
                            Task 17 (Docker + CI)
                            Task 18 (README)
```

Tasks 3-12 can run in **parallel** after Task 2 completes.
