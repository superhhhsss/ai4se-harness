"""主循环 — 7 阶段管道编排."""
from ai4se_harness.llm.base import LLMBackend
from ai4se_harness.config import Config
from ai4se_harness.context import ContextBuilder
from ai4se_harness.parser import ActionParser
from ai4se_harness.guardrail import Guardrail
from ai4se_harness.tools.registry import ToolRegistry
from ai4se_harness.tools import register_file_tools, register_shell_tool, register_test_tool
from ai4se_harness.feedback import FeedbackCollector
from ai4se_harness.stop_judge import StopJudge
from ai4se_harness.memory import MemoryStore
from ai4se_harness.models import StopReason


class Harness:
    def __init__(self, config: Config, llm_backend: LLMBackend,
                 memory: MemoryStore | None = None, workspace: str | None = None):
        self.config = config
        self.llm = llm_backend
        self.memory = memory or MemoryStore()

        self.tools = ToolRegistry()
        register_file_tools(self.tools)
        register_shell_tool(self.tools)
        register_test_tool(self.tools)

        self.parser = ActionParser()
        self.guardrail = Guardrail(patterns=config.guardrail_patterns, workspace=workspace)
        self.feedback = FeedbackCollector(
            auto_test=config.feedback_auto_test,
            auto_lint=config.feedback_auto_lint,
            max_self_correct_rounds=config.feedback_max_self_correct_rounds,
        )
        self.stop_judge = StopJudge(max_rounds=config.loop_max_rounds)
        self.context_builder = ContextBuilder(config=config, memory=self.memory, tools=self.tools)
        self.history: list = []

    def run(self, task: str) -> StopReason:
        self.history = []
        round_count = 0

        while True:
            round_count += 1
            ctx = self.context_builder.build(task, self.history, round_count)

            response = self.llm.chat(ctx.messages, ctx.tools)
            action = self.parser.parse(response, round=round_count)

            if action.tool == "stop":
                reason = self.stop_judge.check(action, None, round_count, self.history)
                if reason.should_stop:
                    return reason

            decision = self.guardrail.check(action)
            if decision.verdict == "BLOCK":
                if not self._handle_block(action, decision):
                    return StopReason(should_stop=True, reason="user_abort")

            result = self.tools.dispatch(action)
            feedback = self.feedback.collect(result, action)
            self.history.append((action, result, feedback))

            reason = self.stop_judge.check(action, feedback, round_count, self.history)
            if reason.should_stop:
                return reason

    def _handle_block(self, action, decision) -> bool:
        print(f"\n[护栏] 已拦截: {decision.reason}")
        print(f"  动作: {action.tool}({action.params})")
        while True:
            choice = input("  [C]确认 / [R]拒绝 / [M]修改: ").strip().lower()
            if choice == "c":
                self.guardrail.allowlist.add(action.params.get("command", ""))
                return True
            elif choice == "r":
                return False
            elif choice == "m":
                new_cmd = input("  新命令: ")
                action.params["command"] = new_cmd
                recheck = self.guardrail.check(action)
                return recheck.verdict != "BLOCK" or self._handle_block(action, recheck)