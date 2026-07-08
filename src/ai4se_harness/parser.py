"""解析 LLM 输出为 Action 对象."""
import ast
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
        except json.JSONDecodeError:
            # Fallback: try Python dict syntax (single quotes)
            try:
                data = ast.literal_eval(raw)
            except (ValueError, SyntaxError) as e:
                raise ParseError(f"LLM 返回非法 JSON: {raw[:200]}") from e
        if not isinstance(data, dict):
            raise ParseError(f"需要 JSON 对象，收到 {type(data).__name__}")

        if "tool" not in data and "stop" not in data:
            raise ParseError("JSON 必须包含 'tool' 或 'stop' 字段")

        return Action(
            tool=data.get("tool", "stop"),
            params=data.get("params", {}),
            raw_llm_output=llm_output,
            round=round,
        )