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

        memories = self.memory.retrieve(task)
        if memories:
            mem_text = "来自之前会话的相关上下文:\n"
            for m in memories:
                mem_text += f"- {m}\n"
            messages.append({"role": "system", "content": mem_text})

        for action, result, feedback in history:
            messages.append({
                "role": "assistant",
                "content": f'{{"tool": "{action.tool}", "params": {action.params}}}'
            })
            fb_text = f"结果: {'PASS' if result.success else 'FAIL'}\n{result.stdout[:1000]}"
            if feedback and not feedback.passed:
                fb_text += f"\n反馈: {feedback.suggestion or feedback.failed_stage}"
            messages.append({"role": "user", "content": fb_text})

        messages.append({
            "role": "user",
            "content": f"任务: {task}\n\n输出下一步动作的 JSON。"
        })

        tools_schema = self.tools.get_tools_schema()
        return Context(
            messages=messages,
            tools=tools_schema if tools_schema else None,
        )