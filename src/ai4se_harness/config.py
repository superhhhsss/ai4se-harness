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