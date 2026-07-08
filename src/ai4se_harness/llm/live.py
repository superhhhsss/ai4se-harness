"""真实 LLM 后端 — 通过 OpenAI 兼容协议调用 DeepSeek."""
import json
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
        msg = response.choices[0].message

        # If the model returns a tool call, serialize it as JSON
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return json.dumps({"tool": tc.function.name, "params": json.loads(tc.function.arguments)})

        return msg.content or ""