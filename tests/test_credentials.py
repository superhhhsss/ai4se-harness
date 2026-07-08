"""凭据管理器测试."""
from unittest.mock import patch
from ai4se_harness.credentials import CredentialManager


def test_get_returns_key_from_keyring():
    with patch("keyring.get_password", return_value="sk-test123"):
        cm = CredentialManager(service_name="test-harness")
        assert cm.get() == "sk-test123"


def test_get_returns_none_when_not_set():
    with patch("keyring.get_password", return_value=None):
        with patch("os.getenv", return_value=None):
            cm = CredentialManager(service_name="test-harness")
            assert cm.get() is None


def test_set_stores_key():
    with patch("keyring.set_password") as mock_set:
        cm = CredentialManager(service_name="test-harness")
        cm.set("sk-abc")
        mock_set.assert_called_once_with("test-harness", "api_key", "sk-abc")


def test_clear_deletes_key():
    with patch("keyring.delete_password") as mock_del:
        cm = CredentialManager(service_name="test-harness")
        cm.clear()
        mock_del.assert_called_once_with("test-harness", "api_key")


def test_status_configured():
    with patch("keyring.get_password", return_value="sk-xxx"):
        cm = CredentialManager(service_name="test-harness")
        status = cm.status()
        assert "已配置" in status
        assert "sk-xxx" not in status  # 绝不可泄漏明文


def test_env_fallback():
    with patch("keyring.get_password", return_value=None):
        with patch("os.getenv", return_value="sk-from-env"):
            cm = CredentialManager(service_name="test-harness")
            assert cm.get() == "sk-from-env"