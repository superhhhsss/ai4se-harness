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