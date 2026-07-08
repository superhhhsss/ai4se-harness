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