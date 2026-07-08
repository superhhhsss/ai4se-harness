# 反思报告

## 一、Superpowers 技能效用评估

### 发挥了最大作用的技能

**brainstorming** 是本次项目中最有价值的技能。它不是简单地"问你想做什么"，而是通过一次一个问题、逐步推进的方式，强迫我把模糊的想法逐层拆解。在讨论 Coding Agent Harness 的架构时，它追问了"你选的六个维度中哪个是重点"、"工具集应该多大"、"分发形态选什么"，这些问题如果我一个人闷头想，大概率会跳过或者堆到最后再纠结。逐层签字的流程让我在写代码之前就把所有关键决策都定下来了。

**writing-plans** 的颗粒度要求（每步 2-5 分钟、明确文件路径、明确验证步骤）让我在写 PLAN 时发现了几个 SPEC 中没写清楚的地方。比如 FeedbackCollector 的构造注入设计，就是在写 PLAN 时意识到"如果 mock 私有方法，那测试就不够干净"，从而在 PLAN 阶段就修正了设计方案。

**TDD 强制**（test-driven-development）在 AI 协作下是放大器而非阻碍。传统观点认为 TDD 拖慢开发速度，但在这个项目中，mock LLM 的测试让我能脱离真实 API 验证所有核心机制。65 个测试在 1.7 秒内跑完，每一次改动后立刻知道有没有破坏什么。这种即时反馈在 AI 生成的代码上尤其重要——因为你不可能逐行审查 subagent 输出的每一段代码，但测试会替你审查。

### 形式大于实质的技能

**using-git-worktrees** 在个人项目中意义有限。worktree 的设计是为了多人并行开发时的隔离，但单人项目里，你不可能同时写两个 task 还 merge 自己。我最终没有为每个 task 开 worktree，而是按依赖关系串行推进，只在逻辑上保持了"一个 task 一个 commit"的纪律。

**visual-companion**（brainstorming 的浏览器可视化）在本项目中用途有限。这是一个纯后端/CLI 项目，唯一的可视化需求是架构管道图。画了一张图之后，后续所有讨论都在终端里完成。对于前端项目这可能很有用，但对 harness 类项目，终端对话更高效。

## 二、Subagent-Driven 工作流评估

我在本项目中主要使用串行实现（inline execution）而非 subagent 派发。原因是：

1. **依赖链条长**：Task 2（数据模型）→ Tasks 3-12（各模块）→ Task 13（context）→ Task 14（loop）→ Task 15（CLI），后面每个 task 都依赖前面的接口定义。如果前一个 task 的接口变了，后面所有 subagent 的工作都要重做。

2. **上下文传递成本**：每个 subagent 都是从零开始的新会话，需要我口头解释项目背景。而 PLAN 虽然详细，但 subagent 对 PLAN 的解读可能和我的预期不一致——这也是冷启动验证暴露的问题（build-backend 写错）。

3. **task 颗粒度**：我发现最优的 task 颗粒度是"一个可独立编译/测试的模块"，大约 50-100 行实现代码 + 等量测试代码。比这个更小（如"写一个函数"）会产生太多碎片化 commit；比这个更大（如"实现整个工具系统"）会让 subagent 偏离主题。

对于 harness 这种接口密集的项目，subagent 工作流更适合在"接口已稳定、实现可并行"的后期阶段使用。早期阶段（定义接口、搭骨架）更适合串行、频繁验证的方式。

## 三、SPEC / PLAN 质量对实现质量的影响

冷启动验证中暴露了一个典型案例：`build-backend` 写成了 `setuptools.backends._legacy:_Backend`（不存在的模块），正确值应该是 `setuptools.build_meta`。这个错误在 SPEC 层面完全不可见——SPEC 只说"技术栈 Python 3.12"，不涉及 PEP 517 细节。但 PLAN 中一个字符的错误就导致 `pip install -e .` 直接报错，陌生 agent 会在第一步卡死。

另一个例子：PLAN 中 FeedbackCollector 最初的设计是通过 mock 私有方法 `_run_tests` / `_run_lint` 来测试。在写 PLAN 时我意识到这不够干净，改成了构造注入（`test_runner` / `lint_runner` 参数）。这个改动如果在实现阶段才发现，需要重构整个 FeedbackCollector 的接口。但在 PLAN 阶段改动，成本为零。

教训：**SPEC 管"做什么"，PLAN 管"怎么做"。SPEC 的错误导致方向偏差，PLAN 的错误导致执行阻塞。** 两者都重要，但 PLAN 的 bug 更隐蔽（因为往往是一个字符、一个路径、一个参数名），更需要冷启动验证来暴露。

## 四、最有效的 Prompt / Context 策略

在本项目中，最有效的策略是**在 mock LLM 测试中精确构造 context 验证**。比如 `test_demo2_feedback_drives_self_correction` 中，我构造了一个三阶段的 mock LLM 响应序列（写 bug 代码 → 收到反馈 → 写修正代码 → 停止），然后注入一个分阶段的 feedback collector，精确验证了反馈闭环的完整链路。这种测试的价值在于：它不是在测试"LLM 是否聪明"，而是在测试"harness 是否正确地把反馈传递给了 LLM"。

另一个有效策略是**在 system prompt 中保持极简**。我最初的 system prompt 写了 15 行，包含了各种"你应该..."的指导。后来砍到 5 行，只保留核心的 JSON 格式要求。因为真正的约束（护栏、反馈、停机）已经由代码机制保证了，system prompt 里的提醒是冗余的，而且无法测试。

## 五、凭据与分发的工程价值

凭据安全的要求迫使我认真思考了"用户的 API key 到底放在哪里"这个问题。最初的想法是"就放 .env 里"，但课程要求必须实现安全存储（keyring）+ 说明 .env 的明文风险。这个要求让我意识到：**真正被使用的工具，安全设计不能依赖"用户会小心"的假设。** keyring 接入成本很低（Python `keyring` 库 5 行代码），但安全性提升是质变的。

分发要求（Docker + PyPI）让我提前思考了"别人怎么用我的东西"这个问题。Docker 的 `docker run` 命令和 PyPI 的 `pip install` 命令需要在 README 中写清楚，而且 key 在容器中如何配置（`-e DEEPSEEK_API_KEY=xxx`）也需要文档化。这个流程走一遍后，我理解了为什么开源项目都要配 Dockerfile 和 CI——因为它们让"能跑"从一个主观判断变成了客观事实。

## 六、如果重做会改变什么

1. **先写 mock LLM 测试，再写主循环**。我现在的顺序是 models → 各模块 → context → loop → demo。但 demo 测试（尤其是 test_demo2）其实是对整个 harness 的集成验证。如果我先写 demo 测试，它会在所有模块就绪之前就失败，从而驱动我更快地完成各模块——这是 TDD 在项目级别的应用。

2. **减少 parser 的容错性**。现在的 parser 对 LLM 输出的格式非常宽容（自动剥离 markdown fence、默认 tool 为 stop），但这意味着 LLM 的格式错误不会在系统中留下可见痕迹。应该加一个 `--strict` 模式，在开发/调试阶段拒绝非标准 JSON。

3. **更早做冷启动验证**。我在 PLAN 写完后做了冷启动验证，发现了 build-backend 错误。但如果我在 SPEC 写完后、PLAN 写之前先用另一个 agent 试跑 SPEC，可能会在更早的阶段发现更多问题。

## 七、对 Superpowers 方法论的批判

Superpowers 的核心假设是：**流程纪律（brainstorming → writing-plans → TDD → review → finishing）能弥补 AI 编码的不确定性。** 这个假设在我的项目中基本成立——TDD 和 code review 确实捕捉到了 AI 生成代码中的多个问题（parser 对缺失 tool 字段的处理、guardrail 的 workspace 检查逻辑等）。

但 Superpowers 的另一个隐含假设是：**每个项目都可以被分解为 2-5 分钟的独立 task。** 这个假设在 harss 类项目中不完全成立。因为 harness 的各个模块之间接口耦合紧密——loop 依赖 context、context 依赖 memory + tools、tools 依赖 models——你很难在不定义接口的情况下独立实现任何一个模块。PLAN 中的"Tasks 3-12 可并行"是基于"接口已在 Task 2 中定义"的前提，但实际实现中，接口往往在实现过程中才会被修正（比如 Guardrail 需要 workspace 参数，这个需求在写 loop 时才发现）。

最后，Superpowers 的 seven-step workflow 在个人项目中有些过度工程化。finishing-a-development-branch 和 using-git-worktrees 对于单人项目是多余的。但 brainstorming → writing-plans → TDD → review 这四个核心步骤确实显著提升了代码质量。如果让我给这套方法论打分，我会说：**核心四步 9/10，完整七步 6/10（个人项目）。**