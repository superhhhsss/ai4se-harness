"""上下文构建器 — 拼装 system prompt + 记忆 + 历史 + 反馈."""
import json
from dataclasses import dataclass
from ai4se_harness.config import Config
from ai4se_harness.memory import MemoryStore
from ai4se_harness.tools.registry import ToolRegistry


@dataclass
class Context:
    messages: list[dict]
    tools: list[dict] | None


SYSTEM_PROMPT = """You are a coding assistant. Use the available tools to read/write files, run shell commands, and execute tests. Complete each task step by step. When the task is done, call no more tools and simply respond with 'stop'."""


class ContextBuilder:
    def __init__(self, config: Config, memory: MemoryStore, tools: ToolRegistry):
        self.config = config
        self.memory = memory
        self.tools = tools
        self._tool_call_id = 0

    def build(self, task: str, history: list, round_count: int) -> Context:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        memories = self.memory.retrieve(task)
        if memories:
            mem_text = "Relevant context from past sessions:\n"
            for m in memories:
                mem_text += f"- {m}\n"
            messages.append({"role": "system", "content": mem_text})

        for action, result, feedback in history:
            tool_name = action.tool
            if tool_name == "stop":
                messages.append({"role": "assistant", "content": "stop"})
                continue

            self._tool_call_id += 1
            call_id = f"call_{self._tool_call_id}"

            # Assistant message with tool_calls
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(action.params, ensure_ascii=False)
                    }
                }]
            })

            # Tool result message
            fb_text = f"Result: {'PASS' if result.success else 'FAIL'}\nstdout: {result.stdout[:1000]}\nstderr: {result.stderr[:500]}"
            if feedback and not feedback.passed:
                fb_text += f"\nFeedback: {feedback.suggestion or feedback.failed_stage}"
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": fb_text
            })

        messages.append({
            "role": "user",
            "content": f"Task: {task}\n\nProceed with the next step."
        })

        tools_schema = self.tools.get_tools_schema()
        return Context(
            messages=messages,
            tools=tools_schema if tools_schema else None,
        )