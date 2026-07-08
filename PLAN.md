# Coding Agent Harness 实现计划

> **供 agent 执行者使用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按 task 逐个实现。每步使用 checkbox（`- [ ]`）跟踪进度。

**目标：** 构建一个 CLI 交互式 Coding Agent Harness，采用管道架构。包含：上下文构建、LLM 调用、动作解析、护栏（HITL）、工具分发、反馈收集（主要贡献）、停机判断。所有核心机制均可通过 mock LLM 做确定性单元测试验证。

**架构：** 7 阶段中间件管道（Context → LLM → Parser → Guardrail → Dispatch → Feedback → Stop）+ 3 个侧通道（Memory、Config、Credentials）。每阶段独立可测，通过明确定义的输入/输出接口解耦。

**反馈闭环设计说明：** 反馈闭环的工作方式是"间接驱动"——FeedbackCollector 收集客观测试/校验结果后，将结构化的 Feedback 对象注入下一轮的 Context（由 Context Builder 负责拼接），LLM 在下一轮看到反馈信息后自主决定修正策略。这不是"harness 自己改代码"，而是"harness 把客观信号传递给 LLM，让它做更好的下一步决策"。自我修正次数由配置 `max_self_correct_rounds` 控制。

**技术栈：** Python 3.12、openai SDK（兼容 DeepSeek）、SQLite、keyring、pytest、Click CLI、PyYAML。

---

## Task 1: 项目脚手架

**涉及文件：**
- 新建：`pyproject.toml`、`Makefile`、`config.yaml`
- 新建：`src/ai4se_harness/__init__.py`、`tests/__init__.py`

- [ ] **Step 1: 编写 pyproject.toml**

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

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "flake8>=7.0",
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

- [ ] **Step 2: 编写 Makefile**

```makefile
.PHONY: test lint install cov demo

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

- [ ] **Step 3: 编写 config.yaml**

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

- [ ] **Step 4: 创建空的 `__init__.py`**

```bash
echo '"AI4SE Coding Agent Harness."' > src/ai4se_harness/__init__.py
echo '"Tests for AI4SE Harness."' > tests/__init__.py
```

- [ ] **Step 5: 安装并验证**

```bash
pip install -e .
python -c "import ai4se_harness; print('OK')"
```
预期输出: `OK`

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml Makefile config.yaml src/ai4se_harness/__init__.py tests/__init__.py
git commit -m "feat: 项目脚手架 — pyproject.toml, Makefile, config.yaml"
```

---

## Task 2: 数据模型

**涉及文件：**
- 新建：`src/ai4se_harness/models.py`、`tests/test_models.py`

- [ ] **Step 1: 编写失败测试**

```python
"""数据模型测试."""
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
    gd = GuardDecision(verdict="BLOCK", reason="危险: rm -rf /", matched_pattern=r"rm\s+(-rf?)")
    assert gd.verdict == "BLOCK"
    assert gd.matched_pattern is not None


def test_stop_reason_completed():
    sr = StopReason(should_stop=True, reason="task_completed")
    assert sr.should_stop is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_models.py -v
```
预期：全部 FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 编写 models.py**

```python
"""Coding Agent Harness 数据模型."""
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
    failed_stage: str | None = None  # "compile" | "test" | "lint"
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

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_models.py -v
```
预期：全部 6 个 PASS

- [ ] **Step 5: 提交**

```bash
git add src/ai4se_harness/models.py tests/test_models.py
git commit -m "feat: 添加数据模型 (Action, ActionResult, Feedback, GuardDecision, StopReason)"
```

---

## Task 3: 配置模块

**涉及文件：**
- 新建：`src/ai4se_harness/config.py`、`tests/test_config.py`

- [ ] **Step 1: 编写失败测试**

```python
"""配置模块测试."""
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

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 3: 编写 config.py**

```python
"""从 YAML 文件加载配置."""
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

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/ai4se_harness/config.py tests/test_config.py
git commit -m "feat: 添加配置模块 (YAML 加载器)"
```

---

## Task 4: 凭据管理器

**涉及文件：**
- 新建：`src/ai4se_harness/credentials.py`、`tests/test_credentials.py`

- [ ] **Step 1: 编写失败测试**

```python
"""凭据管理器测试."""
from unittest.mock import patch
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
        assert "已配置" in status
        assert "sk-xxx" not in status  # 绝不可泄漏明文


def test_env_fallback():
    with patch("keyring.get_password", return_value=None):
        with patch("os.getenv", return_value="sk-from-env"):
            cm = CredentialManager(service_name="test-harness")
            assert cm.get() == "sk-from-env"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_credentials.py -v
```

- [ ] **Step 3: 编写 credentials.py**

```python
"""凭据管理 — 系统钥匙串为主，环境变量为 fallback."""
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
            return "API key 已配置 (DeepSeek)"
        return "API key 未配置。请运行 'ai4se-harness key setup'"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_credentials.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/ai4se_harness/credentials.py tests/test_credentials.py
git commit -m "feat: 添加凭据管理器 (keyring + env fallback)"
```

---

## Task 5: LLM 抽象层

**涉及文件：**
- 新建：`src/ai4se_harness/llm/__init__.py`、`base.py`、`mock.py`、`live.py`
- 新建：`tests/test_llm.py`

- [ ] **Step 1: 编写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_llm.py -v
```

- [ ] **Step 3: 编写 llm/base.py**

```python
"""LLM 抽象基类."""
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """发送消息到 LLM，返回补全文本."""
        ...
```

- [ ] **Step 4: 编写 llm/mock.py**

```python
"""Mock LLM — 确定性测试的核心."""
from ai4se_harness.llm.base import LLMBackend


class MockLLMBackend(LLMBackend):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        if self.call_count >= len(self.responses):
            raise IndexError(f"Mock 响应耗尽 (已用 {self.call_count}/{len(self.responses)})")
        self.calls.append(messages)
        response = self.responses[self.call_count]
        self.call_count += 1
        return response
```

- [ ] **Step 5: 编写 llm/live.py**

```python
"""真实 LLM 后端 — 通过 OpenAI 兼容协议调用 DeepSeek."""
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
            model=self.model, messages=messages,
            max_tokens=self.max_tokens, temperature=self.temperature,
        )
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
```

- [ ] **Step 6: 编写 llm/__init__.py**

```python
"""LLM 抽象层."""
from ai4se_harness.llm.base import LLMBackend
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.llm.live import LiveLLMBackend

__all__ = ["LLMBackend", "MockLLMBackend", "LiveLLMBackend"]
```

- [ ] **Step 7: 运行测试确认通过并提交**

```bash
pytest tests/test_llm.py -v
git add src/ai4se_harness/llm/ tests/test_llm.py
git commit -m "feat: 添加 LLM 抽象层 (base, mock, live)"
```

---

## Task 6: 记忆存储

**涉及文件：**
- 新建：`src/ai4se_harness/memory.py`、`tests/test_memory.py`

- [ ] **Step 1: 编写失败测试**

```python
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
    result = memory.retrieve("python style")
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

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_memory.py -v
```

- [ ] **Step 3: 编写 memory.py**

```python
"""基于 SQLite 的跨会话记忆存储."""
import json
import sqlite3


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

- [ ] **Step 4: 运行测试确认通过并提交**

```bash
pytest tests/test_memory.py -v
git add src/ai4se_harness/memory.py tests/test_memory.py
git commit -m "feat: 添加 SQLite 记忆存储"
```

---

## Task 7: 动作解析器

**涉及文件：**
- 新建：`src/ai4se_harness/parser.py`、`tests/test_parser.py`

- [ ] **Step 1: 编写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败，编写 parser.py**

```python
"""解析 LLM 输出为 Action 对象."""
import json
import re
from ai4se_harness.models import Action


class ParseError(Exception):
    """LLM 输出无法解析为 Action."""
    pass


class ActionParser:
    def parse(self, llm_output: str, round: int = 0) -> Action:
        raw = llm_output.strip()
        fence_match = re.match(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParseError(f"LLM 返回非法 JSON: {raw[:200]}") from e
        if not isinstance(data, dict):
            raise ParseError(f"需要 JSON 对象，收到 {type(data).__name__}")
        return Action(
            tool=data.get("tool", "stop"),
            params=data.get("params", {}),
            raw_llm_output=llm_output,
            round=round,
        )
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_parser.py -v
git add src/ai4se_harness/parser.py tests/test_parser.py
git commit -m "feat: 添加动作解析器 (JSON 提取 + 验证)"
```

---

## Task 8: 工具注册表

**涉及文件：**
- 新建：`src/ai4se_harness/tools/__init__.py`、`registry.py`
- 新建：`tests/test_tools.py`

- [ ] **Step 1: 编写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败，编写 registry.py**

```python
"""工具注册表."""
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
            raise ValueError(f"未知工具: {action.tool}")
        return self._tools[action.tool](action)

    def get_tools_schema(self) -> list[dict]:
        return [{"type": "function", "function": s} for s in self._schemas.values()]
```

- [ ] **Step 3: 编写 tools/__init__.py，测试通过并提交**

```python
"""Harness 内置工具."""
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.tools.file_tools import register_file_tools
from ai4se_harness.tools.shell_tool import register_shell_tool
from ai4se_harness.tools.test_tool import register_test_tool

__all__ = ["ToolRegistry", "register_file_tools", "register_shell_tool", "register_test_tool"]
```

```bash
pytest tests/test_tools.py -v
git add src/ai4se_harness/tools/ tests/test_tools.py
git commit -m "feat: 添加工具注册表 (注册 + 分发 + schema 生成)"
```

---

## Task 9: 内置工具实现

**涉及文件：**
- 新建：`src/ai4se_harness/tools/file_tools.py`、`shell_tool.py`、`test_tool.py`
- 修改：`tests/test_tools.py`（新增集成测试）

- [ ] **Step 1: 编写 file_tools.py**

```python
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
```

- [ ] **Step 2: 编写 shell_tool.py**

```python
"""Shell 执行工具."""
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
        return ActionResult(success=False, stdout="", stderr="命令超时 (120s)",
                           exit_code=-1, duration_ms=int((time.monotonic() - t0) * 1000))


def register_shell_tool(registry: ToolRegistry) -> None:
    registry.register("run_shell", run_shell, {
        "name": "run_shell", "description": "执行 shell 命令",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录"}
            },
            "required": ["command"]
        }
    })
```

- [ ] **Step 3: 编写 test_tool.py**

```python
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
```

- [ ] **Step 4: 在 test_tools.py 中追加集成测试**

```python
def test_all_tools_integration(tmp_path):
    from ai4se_harness.tools.registry import ToolRegistry
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
```

- [ ] **Step 5: 测试通过并提交**

```bash
pytest tests/test_tools.py -v
git add src/ai4se_harness/tools/file_tools.py src/ai4se_harness/tools/shell_tool.py src/ai4se_harness/tools/test_tool.py tests/test_tools.py
git commit -m "feat: 添加内置工具 (文件读写, shell, 测试运行)"
```

---

## Task 10: 护栏

**涉及文件：**
- 新建：`src/ai4se_harness/guardrail.py`、`tests/test_guardrail.py`

- [ ] **Step 1: 编写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败，编写 guardrail.py**

```python
"""护栏：在危险动作执行前拦截."""
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
        if action.tool == "write_file":
            return self._check_write(action)
        if action.tool in ("read_file", "run_test"):
            return GuardDecision(verdict="ALLOW", reason="安全工具")
        if action.tool == "run_shell":
            return self._check_shell(action)
        return GuardDecision(verdict="ALLOW", reason="未知工具 — 放行")

    def _check_shell(self, action: Action) -> GuardDecision:
        command = action.params.get("command", "")
        if command in self.allowlist:
            return GuardDecision(verdict="ALLOW", reason="在白名单中")
        for pattern in self.patterns:
            if re.search(pattern, command):
                return GuardDecision(
                    verdict="BLOCK",
                    reason=f"匹配危险模式: {pattern}",
                    matched_pattern=pattern,
                )
        return GuardDecision(verdict="ALLOW", reason="安全的 shell 命令")

    def _check_write(self, action: Action) -> GuardDecision:
        path = Path(action.params.get("path", "")).resolve()
        workspace_path = Path(self.workspace).resolve()
        try:
            path.relative_to(workspace_path)
            return GuardDecision(verdict="ALLOW", reason="路径在工作区内")
        except ValueError:
            return GuardDecision(
                verdict="BLOCK",
                reason=f"写入路径超出工作区: {path}",
                matched_pattern="path_escape",
            )
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_guardrail.py -v
git add src/ai4se_harness/guardrail.py tests/test_guardrail.py
git commit -m "feat: 添加护栏 (正则匹配 + 工作区边界)"
```

---

## Task 11: 反馈收集器 ★（重点维度）

**涉及文件：**
- 新建：`src/ai4se_harness/feedback.py`、`tests/test_feedback.py`

> **设计说明：** FeedbackCollector 通过构造注入 `test_runner` 和 `lint_runner` 可调用对象。生产环境默认用 subprocess 跑 pytest/flake8；测试时直接注入返回预设结果的 lambda，无需 mock 私有方法。这满足 §A.4(C) 的"移除真实 LLM/外部进程后仍可确定性单测"要求。

- [ ] **Step 1: 编写失败测试**

```python
"""反馈收集器测试 — 重点维度."""
import subprocess
from ai4se_harness.feedback import FeedbackCollector, parse_lint_output
from ai4se_harness.models import Action, ActionResult


def make_test_runner(returncode: int, stdout: str, stderr: str):
    """创建模拟的 test_runner."""
    def runner(path=None):
        return subprocess.CompletedProcess(args=[], returncode=returncode,
                                           stdout=stdout, stderr=stderr)
    return runner


def make_lint_runner(output: str):
    """创建模拟的 lint_runner."""
    def runner(files):
        return output
    return runner


# --- 基础收集 ---

def test_collect_test_failure():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "1 failed", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["test_a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "test_a.py"}))
    assert fb.passed is False
    assert fb.failed_stage == "test"
    assert fb.test_report == "1 failed"


def test_collect_lint_issues():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "OK", ""),
        lint_runner=make_lint_runner("a.py:1:1: E302 expected 2 blank lines"),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert fb.passed is False
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_collect_all_pass():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "2 passed", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["a.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "a.py"}))
    assert fb.passed is True
    assert fb.failed_stage is None


def test_collect_skips_for_read_actions():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAIL", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="content", stderr="", exit_code=0)
    fb = collector.collect(result, Action(tool="read_file", params={"path": "x.py"}))
    assert fb.passed is True  # 读文件不触发测试


def test_collect_skips_non_python_files():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAIL", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["README.md"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "README.md"}))
    assert fb.passed is True  # 非 Python 文件不触发


# --- 失败分类 ---

def test_classify_compile_error():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "", "SyntaxError: invalid syntax"),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["broken.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "broken.py"}))
    assert fb.failed_stage == "compile"
    assert "syntax" in fb.suggestion.lower()


def test_classify_test_failure():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "FAILED test_x.py::test_foo - assert 1 == 2", ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["foo.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "foo.py"}))
    assert fb.failed_stage == "test"
    assert "pytest" in fb.suggestion.lower()


def test_classify_lint_error():
    collector = FeedbackCollector(
        test_runner=make_test_runner(0, "OK", ""),
        lint_runner=make_lint_runner("x.py:1:1: F401 imported but unused"),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "x.py"}))
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1


def test_suggestion_truncates_long_report():
    collector = FeedbackCollector(
        test_runner=make_test_runner(1, "X" * 1000, ""),
        lint_runner=make_lint_runner(""),
    )
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["big.py"])
    fb = collector.collect(result, Action(tool="write_file", params={"path": "big.py"}))
    assert len(fb.suggestion) < 600  # 截断


# --- 自修正轮数跟踪 ---

def test_correct_round_tracking():
    collector = FeedbackCollector(max_self_correct_rounds=3)
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    action = Action(tool="write_file", params={"path": "x.py"})

    collector._run_tests = make_test_runner(1, "FAIL", "")
    collector._run_lint = make_lint_runner("")

    for i in range(3):
        fb = collector.collect(result, action)
        assert fb.passed is False
    assert collector.is_stuck("x.py") is True


def test_correct_round_resets_on_pass():
    collector = FeedbackCollector(max_self_correct_rounds=3)
    result = ActionResult(success=True, stdout="", stderr="", exit_code=0,
                          files_changed=["x.py"])
    action = Action(tool="write_file", params={"path": "x.py"})

    collector._run_tests = make_test_runner(1, "FAIL", "")
    collector._run_lint = make_lint_runner("")
    collector.collect(result, action)

    collector._run_tests = make_test_runner(0, "OK", "")
    collector._run_lint = make_lint_runner("")
    collector.collect(result, action)

    assert collector.is_stuck("x.py") is False


# --- Lint 输出解析 ---

def test_parse_lint_output():
    output = "a.py:1:1: F401 'os' imported but unused\nb.py:5:10: E302 expected 2 blank lines"
    issues = parse_lint_output(output)
    assert len(issues) == 2
    assert issues[0] == {"file": "a.py", "line": 1, "column": 1, "message": "F401 'os' imported but unused"}
    assert issues[1]["file"] == "b.py"
```

- [ ] **Step 2: 运行确认失败，编写 feedback.py**

```python
"""反馈收集器 — 确定性质量信号提取（主要贡献）.

核心设计：通过构造注入 test_runner / lint_runner，在生产环境中它们默认执行
subprocess 调用 pytest/flake8；在测试中注入返回预设值的 callable，无需 mock 私有方法。
所有分类逻辑（语法错 vs 测试失败 vs lint 警告）为纯函数，完全确定性。
"""
import re
import subprocess
from typing import Callable
from ai4se_harness.models import Action, ActionResult, Feedback


def _default_test_runner(path: str | None = None):
    target = path or "tests/"
    return subprocess.run(["pytest", target, "-v"], capture_output=True, text=True)


def _default_lint_runner(files: list[str]) -> str:
    try:
        result = subprocess.run(
            ["flake8"] + files + ["--max-line-length=120", "--ignore=E501,W503"],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return ""


def parse_lint_output(output: str) -> list[dict]:
    """解析 flake8 输出为结构化列表."""
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


class FeedbackCollector:
    def __init__(self, auto_test: bool = True, auto_lint: bool = True,
                 max_self_correct_rounds: int = 3,
                 test_runner: Callable | None = None,
                 lint_runner: Callable | None = None):
        self.auto_test = auto_test
        self.auto_lint = auto_lint
        self.max_self_correct_rounds = max_self_correct_rounds
        self._run_tests = test_runner or _default_test_runner
        self._run_lint = lint_runner or _default_lint_runner
        self.correct_round_count: dict[str, int] = {}

    def collect(self, result: ActionResult, action: Action) -> Feedback:
        # 只对写文件和 shell 操作收集反馈
        if action.tool not in ("write_file", "run_shell"):
            return Feedback(passed=True)

        files = result.files_changed or action.params.get("path", "")
        if isinstance(files, str):
            files = [files]

        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return Feedback(passed=True, test_report="无 Python 文件变更")

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
                lint_issues = parse_lint_output(lint_output)

        # 失败分类
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

        # 跟踪自修正轮数
        task_key = action.params.get("path", "unknown")
        if not passed:
            self.correct_round_count[task_key] = self.correct_round_count.get(task_key, 0) + 1
        else:
            self.correct_round_count.pop(task_key, None)

        return Feedback(
            passed=passed, test_report=test_report,
            lint_issues=lint_issues, failed_stage=failed_stage,
            suggestion=suggestion,
        )

    def is_stuck(self, task_identifier: str) -> bool:
        return self.correct_round_count.get(task_identifier, 0) >= self.max_self_correct_rounds

    def _build_suggestion(self, failed_stage: str, report: str) -> str:
        if failed_stage == "compile":
            return f"语法错误。修复 Python 语法后重试。\n\n{report[:500]}"
        elif failed_stage == "test":
            return f"测试失败。查看 pytest 输出，定位失败断言并修复代码。\n\n{report[:500]}"
        elif failed_stage == "lint":
            return "代码风格问题。修复 lint 错误后重试。"
        return ""
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_feedback.py -v
git add src/ai4se_harness/feedback.py tests/test_feedback.py
git commit -m "feat: 添加反馈收集器 — 失败分类 + 构造注入 (主要贡献)"
```

---

## Task 12: 停机判断

**涉及文件：**
- 新建：`src/ai4se_harness/stop_judge.py`、`tests/test_stop_judge.py`

- [ ] **Step 1: 编写失败测试**

```python
"""停机判断测试."""
from ai4se_harness.stop_judge import StopJudge
from ai4se_harness.models import Action, ActionResult, Feedback


def test_stops_on_explicit_stop():
    judge = StopJudge(max_rounds=20)
    reason = judge.check(Action(tool="stop", params={}), feedback=None, round_count=3, history=[])
    assert reason.should_stop is True
    assert reason.reason == "task_completed"


def test_stops_on_max_rounds():
    judge = StopJudge(max_rounds=5)
    reason = judge.check(Action(tool="run_shell", params={}), feedback=None,
                         round_count=5, history=[])
    assert reason.should_stop is True
    assert reason.reason == "max_rounds"


def test_continues_within_rounds():
    judge = StopJudge(max_rounds=20)
    reason = judge.check(Action(tool="write_file", params={}), feedback=None,
                         round_count=3, history=[])
    assert reason.should_stop is False


def test_detects_stuck():
    judge = StopJudge(max_rounds=20)
    history = [
        (Action(tool="write_file", params={"path": "a.py"}, round=i),
         ActionResult(success=True, stdout="", stderr="", exit_code=0),
         Feedback(passed=True))
        for i in range(1, 4)
    ]
    reason = judge.check(action=history[-1][0], feedback=history[-1][2],
                         round_count=3, history=history)
    assert reason.should_stop is True
    assert reason.reason == "stuck"
```

- [ ] **Step 2: 运行确认失败，编写 stop_judge.py**

```python
"""停机条件判断."""
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
        first = recent[0][0]
        for a, _, _ in recent[1:]:
            if a.tool != first.tool or a.params != first.params:
                return False
        return True
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_stop_judge.py -v
git add src/ai4se_harness/stop_judge.py tests/test_stop_judge.py
git commit -m "feat: 添加停机判断 (任务完成, 最大轮数, 停滞检测)"
```

---

## Task 13: 上下文构建器

**涉及文件：**
- 新建：`src/ai4se_harness/context.py`、`tests/test_context.py`

- [ ] **Step 1: 编写失败测试**

```python
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
    last_msg = ctx.messages[-1]["content"]
    assert "修复断言" in last_msg
```

- [ ] **Step 2: 运行确认失败，编写 context.py**

```python
"""上下文构建器 — 拼装 system prompt + 记忆 + 历史 + 反馈."""
from dataclasses import dataclass
from ai4se_harness.config import Config
from ai4se_harness.memory import MemoryStore
from ai4se_harness.tools.registry import ToolRegistry


@dataclass
class Context:
    messages: list[dict]
    tools: list[dict] | None


SYSTEM_PROMPT = """你是一个编程助手。你可以使用工具读取/写入文件、执行 shell 命令和运行测试。
每一步输出一个 JSON 对象：

{"tool": "<工具名>", "params": {...}}
或 {"stop": true} 表示任务完成。

只输出合法 JSON，JSON 之外不要有任何解释。"""


class ContextBuilder:
    def __init__(self, config: Config, memory: MemoryStore, tools: ToolRegistry):
        self.config = config
        self.memory = memory
        self.tools = tools

    def build(self, task: str, history: list, round_count: int) -> Context:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 注入相关记忆
        memories = self.memory.retrieve(task)
        if memories:
            mem_text = "来自之前会话的相关上下文:\n"
            for m in memories:
                mem_text += f"- {m}\n"
            messages.append({"role": "system", "content": mem_text})

        # 注入对话历史（含反馈）
        for action, result, feedback in history:
            messages.append({
                "role": "assistant",
                "content": f'{{"tool": "{action.tool}", "params": {action.params}}}'
            })
            fb_text = f"结果: {'PASS' if result.success else 'FAIL'}\n{result.stdout[:1000]}"
            if feedback and not feedback.passed:
                fb_text += f"\n反馈: {feedback.suggestion or feedback.failed_stage}"
            messages.append({"role": "user", "content": fb_text})

        # 当前任务
        messages.append({
            "role": "user",
            "content": f"任务: {task}\n\n输出下一步动作的 JSON。"
        })

        tools_schema = self.tools.get_tools_schema()
        return Context(
            messages=messages,
            tools=tools_schema if tools_schema else None,
        )
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_context.py -v
git add src/ai4se_harness/context.py tests/test_context.py
git commit -m "feat: 添加上下文构建器 (记忆注入 + 历史 + 反馈组装)"
```

---

## Task 14: 主循环

**涉及文件：**
- 新建：`src/ai4se_harness/loop.py`、`tests/test_loop.py`

- [ ] **Step 1: 编写失败测试（使用 tmp_path 避免硬编码路径）**

```python
"""主循环集成测试 (mock LLM)."""
import pytest
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
    h = Harness(config=make_config(), llm_backend=MockLLMBackend([
        f'{{"tool": "write_file", "params": {{"path": "{tmp_path}/test.txt", "content": "hello"}}}}',
        f'{{"tool": "read_file", "params": {{"path": "{tmp_path}/test.txt"}}}}',
        '{"stop": true}',
    ]))
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
```

- [ ] **Step 2: 运行确认失败，编写 loop.py**

```python
"""主循环 — 7 阶段管道编排."""
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
        self.context_builder = ContextBuilder(config=config, memory=self.memory, tools=self.tools)
        self.history: list = []

    def run(self, task: str) -> StopReason:
        self.history = []
        round_count = 0

        while True:
            round_count += 1
            ctx = self.context_builder.build(task, self.history, round_count)

            response = self.llm.chat(ctx.messages, ctx.tools)
            action = self.parser.parse(response, round=round_count)

            if action.tool == "stop":
                reason = self.stop_judge.check(action, None, round_count, self.history)
                if reason.should_stop:
                    return reason

            decision = self.guardrail.check(action)
            if decision.verdict == "BLOCK":
                if not self._handle_block(action, decision):
                    return StopReason(should_stop=True, reason="user_abort")

            result = self.tools.dispatch(action)
            feedback = self.feedback.collect(result, action)
            self.history.append((action, result, feedback))

            reason = self.stop_judge.check(action, feedback, round_count, self.history)
            if reason.should_stop:
                return reason

    def _handle_block(self, action, decision) -> bool:
        """HITL: 暂停并等待用户确认/拒绝/修改."""
        print(f"\n[护栏] 已拦截: {decision.reason}")
        print(f"  动作: {action.tool}({action.params})")
        while True:
            choice = input("  [C]确认 / [R]拒绝 / [M]修改: ").strip().lower()
            if choice == "c":
                self.guardrail.allowlist.add(action.params.get("command", ""))
                return True
            elif choice == "r":
                return False
            elif choice == "m":
                new_cmd = input("  新命令: ")
                action.params["command"] = new_cmd
                recheck = self.guardrail.check(action)
                return recheck.verdict != "BLOCK" or self._handle_block(action, recheck)
```

- [ ] **Step 3: 测试通过并提交**

```bash
pytest tests/test_loop.py -v
git add src/ai4se_harness/loop.py tests/test_loop.py
git commit -m "feat: 添加主循环 (7 阶段管道全部接入)"
```

---

## Task 15: CLI 入口

**涉及文件：**
- 新建：`src/ai4se_harness/cli.py`

- [ ] **Step 1: 编写 cli.py**

```python
"""CLI 入口."""
import click
import getpass
from ai4se_harness.config import Config
from ai4se_harness.llm.live import LiveLLMBackend
from ai4se_harness.credentials import CredentialManager
from ai4se_harness.loop import Harness


@click.group()
def main():
    """AI4SE Coding Agent Harness — LLM 驱动的编码助手，自带护栏与反馈闭环."""
    pass


@main.command()
def run():
    """启动交互式编程助手."""
    creds = CredentialManager()
    api_key = creds.get()
    if not api_key:
        click.echo("未配置 API key。请先运行 'ai4se-harness key setup'")
        raise SystemExit(3)

    config = Config.default()
    llm = LiveLLMBackend(
        api_key=api_key,
        base_url=config.model.get("api_base", "https://api.deepseek.com"),
        model=config.model.get("model", "deepseek-chat"),
    )
    harness = Harness(config=config, llm_backend=llm)

    click.echo("AI4SE Coding Agent Harness 就绪。输入任务 (或 'quit' 退出)。")
    while True:
        task = click.prompt("\nTask", prompt_suffix="> ").strip()
        if task.lower() in ("quit", "exit", "q"):
            break
        reason = harness.run(task)
        click.echo(f"\n已停止: {reason.reason}")


@main.group()
def key():
    """管理 API key."""
    pass


@key.command("setup")
def key_setup():
    """安全存储 API key."""
    creds = CredentialManager()
    api_key = getpass.getpass("输入 DeepSeek API key: ")
    creds.set(api_key)
    click.echo("Key 已保存。")


@key.command("status")
def key_status():
    """查看 API key 状态."""
    click.echo(CredentialManager().status())


@key.command("clear")
def key_clear():
    """删除已存储的 API key."""
    CredentialManager().clear()
    click.echo("Key 已删除。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 CLI 可加载**

```bash
pip install -e .
python -m ai4se_harness.cli --help
```
预期：显示命令组 run, key

- [ ] **Step 3: 提交**

```bash
git add src/ai4se_harness/cli.py
git commit -m "feat: 添加 CLI 入口 (click)"
```

---

## Task 16: 机制演示

**涉及文件：**
- 新建：`tests/test_demo.py`

- [ ] **Step 1: 编写三个演示测试**

```python
"""机制演示 — 全部在 mock LLM 下确定性运行.

演示 1: 护栏拦截危险命令
演示 2: 注入失败 → 反馈回灌 → agent 修正
演示 3: 反馈分类准确度 (主要贡献)
"""
import subprocess
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.loop import Harness
from ai4se_harness.llm.mock import MockLLMBackend
from ai4se_harness.config import Config
from ai4se_harness.models import Action, ActionResult, Feedback


def make_config(**kwargs):
    return Config(
        tools_allowlist=["read_file", "write_file", "run_shell", "run_test"],
        guardrail_patterns=kwargs.get("guardrail_patterns", []),
        feedback_auto_test=False,
        feedback_auto_lint=False,
        feedback_max_self_correct_rounds=3,
        loop_max_rounds=20,
    )


# ====== 演示 1: 护栏拦截 ======

def test_demo1_guardrail_intercepts_dangerous_commands():
    """确定性演示护栏在无真实 LLM 下拦截危险命令."""
    guardrail = Guardrail(patterns=[
        r"rm\s+(-rf?|--recursive)",
        r"DROP\s+(TABLE|DATABASE)",
        r"sudo\s+",
        r">\s*/dev/",
        r"chmod\s+777",
    ])

    # 1a: rm -rf / 被拦截
    action = Action(tool="run_shell", params={"command": "rm -rf / --no-preserve-root"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"
    assert "rm" in decision.reason.lower()

    # 1b: DROP TABLE 被拦截
    action = Action(tool="run_shell", params={"command": "mysql -e 'DROP TABLE users'"})
    decision = guardrail.check(action)
    assert decision.verdict == "BLOCK"

    # 1c: 安全命令放行
    action = Action(tool="run_shell", params={"command": "pytest tests/ -v"})
    decision = guardrail.check(action)
    assert decision.verdict == "ALLOW"

    # 1d: 写工作区外被拦截
    guardrail2 = Guardrail(workspace="/tmp/safe")
    action = Action(tool="write_file", params={"path": "/etc/passwd", "content": "x"})
    decision = guardrail2.check(action)
    assert decision.verdict == "BLOCK"


# ====== 演示 2: 失败注入 → 反馈 → 修正 ======

def test_demo2_feedback_drives_self_correction():
    """注入一次测试失败，验证 agent 接收到 feedback 后修正代码."""
    harness = Harness(
        config=make_config(),
        llm_backend=MockLLMBackend(responses=[
            # 第 1 轮: 写出有 bug 的代码
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a-b"}}',
            # 第 2 轮: 收到反馈后修正
            '{"tool": "write_file", "params": {"path": "calc.py", "content": "def add(a,b): return a+b"}}',
            # 第 3 轮: 完成
            '{"stop": true}',
        ]),
    )

    # 注入反馈：第 1 轮报告失败
    call_count = [0]

    def staged_collect(result, action):
        call_count[0] += 1
        if call_count[0] == 1:
            return Feedback(
                passed=False,
                test_report="FAILED test_calc.py::test_add - assert -1 == 3",
                failed_stage="test",
                suggestion="测试失败: assert add(1,2) == 3, 但得到 -1。应使用 + 而非 -。",
            )
        return Feedback(passed=True)

    harness.feedback.collect = staged_collect

    reason = harness.run("实现一个 add 函数")

    assert reason.reason == "task_completed"
    assert call_count[0] == 2
    # 第 2 轮的写入已修正
    assert harness.history[1][0].params["content"] == "def add(a,b): return a+b"


# ====== 演示 3: 反馈分类准确度 (主要贡献) ======

def test_demo3_feedback_classification():
    """验证反馈收集器正确区分编译错、测试失败和 lint 警告."""
    from ai4se_harness.feedback import FeedbackCollector, parse_lint_output

    def mock_test(rc, stdout, stderr):
        return lambda path=None: subprocess.CompletedProcess(
            args=[], returncode=rc, stdout=stdout, stderr=stderr)

    def mock_lint(output):
        return lambda files: output

    # 场景 A: 语法错 → compile
    collector = FeedbackCollector(
        test_runner=mock_test(1, "", "SyntaxError: invalid syntax"),
        lint_runner=mock_lint(""),
    )
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["bad.py"]),
        Action(tool="write_file", params={"path": "bad.py"})
    )
    assert fb.failed_stage == "compile"
    assert "syntax" in fb.suggestion.lower()

    # 场景 B: 测试失败 → test
    collector._run_tests = mock_test(1, "FAILED test_x.py", "")
    collector._run_lint = mock_lint("")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
        Action(tool="write_file", params={"path": "x.py"})
    )
    assert fb.failed_stage == "test"
    assert "pytest" in fb.suggestion.lower()

    # 场景 C: lint 错误 → lint
    collector._run_tests = mock_test(0, "OK", "")
    collector._run_lint = mock_lint("x.py:1:1: F401 imported but unused")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["x.py"]),
        Action(tool="write_file", params={"path": "x.py"})
    )
    assert fb.failed_stage == "lint"
    assert len(fb.lint_issues) == 1

    # 场景 D: 全部通过 → 无失败
    collector._run_tests = mock_test(0, "3 passed", "")
    collector._run_lint = mock_lint("")
    fb = collector.collect(
        ActionResult(success=True, stdout="", stderr="", exit_code=0, files_changed=["ok.py"]),
        Action(tool="write_file", params={"path": "ok.py"})
    )
    assert fb.passed is True
    assert fb.failed_stage is None
```

- [ ] **Step 2: 运行演示测试**

```bash
pytest tests/test_demo.py -v
```
预期：3 个 demo 测试全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_demo.py
git commit -m "feat: 添加机制演示测试 (护栏拦截, 反馈修正, 分类准确度)"
```

---

## Task 17: Docker + CI

**涉及文件：**
- 新建：`Dockerfile`、`.github/workflows/ci.yml`

- [ ] **Step 1: 编写 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

ENTRYPOINT ["ai4se-harness"]
```

- [ ] **Step 2: 编写 CI 配置**

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

- [ ] **Step 3: 提交**

```bash
git add Dockerfile .github/workflows/ci.yml
git commit -m "feat: 添加 Dockerfile 和 CI (unit-test + docker build)"
```

---

## Task 18: README

**涉及文件：**
- 新建：`README.md`

- [ ] **Step 1: 编写 README.md**

````markdown
# AI4SE Coding Agent Harness

CLI 交互式 Coding Agent Harness，采用管道架构。Agent = LLM + Harness。
所有机制（护栏、反馈、记忆）均为代码实现，不是提示词。

## 快速开始

```bash
pip install -e .
ai4se-harness key setup    # 安全录入 DeepSeek API key
ai4se-harness run          # 启动 agent
```

### Docker

```bash
docker build -t ai4se-harness .
docker run -it -e DEEPSEEK_API_KEY=sk-xxx ai4se-harness run
```

## Key 管理

API key 存储在操作系统钥匙串中，绝不硬编码、不提交 Git。

- `ai4se-harness key setup` — 安全录入
- `ai4se-harness key status` — 查看状态（不回显明文）
- `ai4se-harness key clear` — 删除

环境变量 fallback: `DEEPSEEK_API_KEY`（不推荐明文）。

## 架构

7 阶段管道: Context Builder → LLM Call → Action Parser → Guardrail (HITL) → Tool Dispatch → Feedback Collector → Stop Judge

3 个侧通道: Memory (SQLite), Config (YAML), Credentials (keyring)

主要贡献: 反馈收集器 — 确定性测试/lint 结果解析 + 失败分类 (compile vs test vs lint) + 构造注入设计。

## 开发

```bash
make install    # pip install -e .
make test       # 运行全部测试
make lint       # flake8
make cov        # 覆盖率报告
make demo       # 机制演示测试
```

## 目录结构

```
src/ai4se_harness/    — harness 源码
tests/               — 测试套件 (mock LLM, 确定性)
config.yaml          — 默认配置
```

## 已知限制

- 仅支持 Python 项目测试 (pytest/flake8)
- 单一 LLM 后端 (DeepSeek)；扩展只需实现 LLMBackend
- 不支持流式响应
- 文件写入限制在工作区目录内

## 安全

- API key: 系统钥匙串 (主) 或环境变量 (fallback)
- Shell: 基于正则的危险命令检测
- 文件 IO: 工作区边界强制
- 日志/终端/历史记录中不出现凭据
````

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: 添加 README (安装, 架构, 安全)"
```

---

## 依赖关系图

```
Task 1 (脚手架)
  └── Task 2 (数据模型)
        ├── Task 3 (配置) ────┐
        ├── Task 4 (凭据)     │
        ├── Task 5 (LLM 层) ──┤
        ├── Task 6 (记忆) ────┤
        ├── Task 7 (解析器) ──┤
        ├── Task 8 (工具注册表)│
        │     └── Task 9 (工具实现)
        ├── Task 10 (护栏) ───┤
        ├── Task 11 (反馈) ★──┤  ← 重点维度
        └── Task 12 (停机) ───┤
                              │
                    Task 13 (上下文构建器)
                              │
                    Task 14 (主循环)
                              │
                    Task 15 (CLI 入口)
                              │
                    Task 16 (机制演示)
                    
                    Task 17 (Docker + CI)
                    Task 18 (README)
```

**Task 3~12 在 Task 2 完成后可并行推进。**
