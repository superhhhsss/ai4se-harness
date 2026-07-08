"""LLM 抽象基类."""
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """发送消息到 LLM，返回补全文本."""
        ...