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