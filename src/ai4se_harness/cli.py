"""CLI 入口."""
import click
import getpass
from ai4se_harness.config import Config
from ai4se_harness.llm.live import LiveLLMBackend
from ai4se_harness.credentials import CredentialManager
from ai4se_harness.loop import Harness


@click.group()
def main():
    """AI4SE Coding Agent Harness — LLM 驱动的编码助手，自带护栏与反馈闭环."""
    pass


@main.command()
def run():
    """启动交互式编程助手."""
    creds = CredentialManager()
    api_key = creds.get()
    if not api_key:
        click.echo("未配置 API key。请先运行 'ai4se-harness key setup'")
        raise SystemExit(3)

    config = Config.default()
    workspace = config.model.get("workspace", "./workspace")
    llm = LiveLLMBackend(
        api_key=api_key,
        base_url=config.model.get("api_base", "https://api.deepseek.com"),
        model=config.model.get("model", "deepseek-chat"),
    )
    harness = Harness(config=config, llm_backend=llm, workspace=workspace)

    click.echo("AI4SE Coding Agent Harness 就绪。输入任务 (或 'quit' 退出)。")
    while True:
        task = click.prompt("\nTask", prompt_suffix="> ").strip()
        if task.lower() in ("quit", "exit", "q"):
            break
        reason = harness.run(task)
        click.echo(f"\n已停止: {reason.reason}")


@main.group()
def key():
    """管理 API key."""
    pass


@key.command("setup")
def key_setup():
    """安全存储 API key."""
    creds = CredentialManager()
    api_key = getpass.getpass("输入 DeepSeek API key: ")
    creds.set(api_key)
    click.echo("Key 已保存。")


@key.command("status")
def key_status():
    """查看 API key 状态."""
    click.echo(CredentialManager().status())


@key.command("clear")
def key_clear():
    """删除已存储的 API key."""
    CredentialManager().clear()
    click.echo("Key 已删除。")


if __name__ == "__main__":
    main()