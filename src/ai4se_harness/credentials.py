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