# SPEC — AI4SE Coding Agent Harness

## 1. 问题陈述

**要解决的问题**：构建一个可独立验证工程深度的 Coding Agent Harness——Agent = LLM + Harness。当 LLM 能完成大部分"思考"时，工程师的价值落在 harness 这层工程上。本项目要交付一个自己编码实现的 harness 内核，而非在现成框架上做配置。

**目标用户**：需要在 AI 辅助下进行软件开发的工程师、希望理解 agent 内部机制的 AI4SE 学习者。

**为什么值得做**：Coding 场景的反馈信号（测试、lint、类型检查）是客观、确定、可编码的——这恰好使"机制必须是代码"的要求最容易落实。通过本项目能对 agentic SE 方法论形成第一手的批判性理解。

---

## 2. 用户故事

1. **写代码并自我修正**：作为开发者，我向 harness 下发一个编码任务，harness 写出代码 → 自动运行测试 → 发现失败后自主修改 → 直到测试通过，整个过程我只在危险操作时才被询问。

2. **拦截危险操作**：作为开发者，当 agent 尝试执行 `rm -rf /` 或 `DROP TABLE` 等危险命令时，harness 必须暂停并清楚地告诉我危险原因，等我确认后才继续。

3. **安全配置 API Key**：作为新用户，首次运行 harness 时，我被引导安全地录入 API key（输入隐藏），key 存入系统钥匙串，后续启动自动读取，任何时候都不回显明文。

4. **查看和修改配置**：作为开发者，我可以通过 YAML 配置文件声明性地控制 agent 行为（允许哪些工具、最大自我修正轮数、护栏规则），无需修改源代码。

5. **一键安装运行**：作为用户，我可以 `pip install` 或 `docker run` 一键获取并运行 harness，README 清楚说明 key 的安全配置方式。

6. **跨会话记忆**：作为开发者，harness 在多次会话之间记住我的项目约定和偏好，新任务开始时自动检索相关记忆注入上下文。

---

## 3. 功能规约

### 3.1 主循环

- 输入：用户自然语言任务描述
- 行为：组织上下文 → 调用 LLM → 解析动作 JSON → 护栏检查 → 分发执行 → 收集反馈 → 停机判断 → 循环
- 输出：任务结果 + 退出码
- 错误处理：LLM API 错误重试 3 次（指数退避）；非法 JSON 注入错误提示回 LLM 修正；连续 3 轮相同 action 判定停滞
- 边界：最大轮数可配置（默认 20）

### 3.2 工具模块

- `read_file(path)` — 读取文件内容
- `write_file(path, content)` — 写入文件
- `run_shell(command)` — 执行 shell 命令（受护栏约束）
- `run_test(path=None)` — 运行 pytest
- 所有工具可通过配置白名单启用/禁用
- 工具注册使用装饰器模式，schema 自动生成为 OpenAI function calling 格式

### 3.3 护栏模块

- 基于正则的危险命令匹配：`rm -rf`、`DROP TABLE/DATABASE`、`sudo`、写入 `/dev/`、`chmod 777`
- 路径范围检查：写文件仅允许在工作目录及子目录
- 拦截时 HITL：终端打印警告 → 等待用户输入 `confirm` / `reject` / `modify`
- 用户可将特定模式加入白名单

### 3.4 反馈模块（重点维度）

- 写文件或执行 shell 后自动触发 pytest 和 flake8
- 解析测试/校验输出，生成结构化 Feedback 对象
- 失败分类：`compile`（语法错误）、`test`（测试失败）、`lint`（代码风格）
- 不同失败类型给出不同回灌提示
- 反馈回灌给下一轮 Context Builder，驱动自我修正（最多 3 轮）
- 自我修正成功（测试通过）则继续下一个任务；3 轮仍失败则告知用户

### 3.5 记忆模块

- SQLite 存储键值对记忆
- Context Builder 在每轮开始时按关键词检索 top-3 相关记忆
- 支持 `store / retrieve / forget / list` 操作
- 向量相似度检索可选（sentence-transformers + numpy 余弦相似度，不依赖外部服务）

### 3.6 配置模块

- YAML 配置文件 `config.yaml`
- 可配置项：模型、工具白名单、护栏规则、反馈最大轮数、最大总轮数
- 首次运行自动生成默认配置文件

### 3.7 凭据模块

- 使用 Python `keyring` 库，后端为操作系统原生钥匙串
- 首次运行引导：隐藏输入 → 存入 keyring
- 命令：`key status`（显示配置状态，不回显明文）、`key update`、`key clear`
- `.env` 文件作为 fallback，README 中说明其明文风险

---

## 4. 非功能性需求

- **性能**：单轮 LLM 调用外的管道开销 <200ms；SQLite 检索 <50ms
- **安全**：API key 绝不硬编码、不提交 Git、不写入日志/终端；凭据威胁模型：环境变量注入、日志泄露、配置文件误提交——对策：keyring 为主存储、`.env` 仅 fallback 并标记明文风险、gitignore 覆盖 `.env*`
- **可用性**：CLI 交互式，首次运行有引导流程；错误信息清晰可操作
- **可观测性**：每轮打印当前阶段、LLM 消耗 token 数、耗时；debug 模式可打印完整 prompt

---

## 5. 系统架构

### 管道架构图

```
User Task → Context Builder → LLM Call → Action Parser → Guardrail → Tool Dispatch → Feedback Collector → Stop Judge
                                     ↑                                                                              │
                                     └──────────────────────── loop back ────────────────────────────────────────────┘
```

### 侧通道

- **Memory Store**（SQLite） — Context Builder 按需检索
- **Config**（YAML） — 控制所有模块行为
- **Credential Manager**（keyring） — 安全存储 API key

### 组件接口

- 每个管道阶段是独立函数/类，只依赖输入参数，不直接调用其他阶段
- `LLMBackend` 抽象接口：`chat(messages, tools) → str`，有两个实现：`LiveBackend`（调 DeepSeek API）和 `MockBackend`（返回预设响应序列）

---

## 6. 数据模型

| 实体 | 核心字段 |
|------|---------|
| `Action` | `tool: str`, `params: dict`, `raw_llm_output: str`, `round: int` |
| `ActionResult` | `success: bool`, `stdout: str`, `stderr: str`, `exit_code: int`, `files_changed: list[str]`, `duration_ms: int` |
| `Feedback` | `passed: bool`, `test_report: str\|None`, `lint_issues: list[dict]`, `failed_stage: str\|None`, `suggestion: str\|None` |
| `GuardDecision` | `verdict: ALLOW\|BLOCK\|ASK`, `reason: str`, `matched_pattern: str\|None` |
| `StopReason` | `should_stop: bool`, `reason: task_completed\|max_rounds\|user_abort\|stuck` |

---

## 7. 凭据与分发设计

### 凭据方案

- 主方案：Python `keyring` 库 → 操作系统原生钥匙串
- Fallback：`.env` 文件（明文，README 说明风险）
- 命令：`ai4se-harness key [status|update|clear]`

### 分发方案

**Docker：**
```bash
docker pull ghcr.io/superhhhsss/ai4se-harness:latest
docker run -it ai4se-harness
```
key 通过环境变量 `-e DEEPSEEK_API_KEY=xxx` 传入或容器内 keyring 引导录入。

**PyPI：**
```bash
pip install ai4se-harness
ai4se-harness
```

CI/CD：GitHub Actions 在 push 时运行测试 + 构建 Docker 镜像 + 发布 PyPI 包。

---

## 8. 技术选型与理由

| 项 | 选择 | 理由 |
|----|------|------|
| 语言 | Python 3.12 | LLM SDK 生态最成熟，mock 机制现成，keyring/pytest 完善 |
| LLM SDK | `openai` | OpenAI 兼容协议，DeepSeek 直接可用，mock 最简单 |
| LLM 供应商 | DeepSeek v4 Pro | 兼容 OpenAI 协议，成本低 |
| 存储 | SQLite | 零依赖、单文件、够用 |
| keyring | `keyring` | 跨平台原生钥匙串，一次适配 |
| 测试 | pytest + pytest-cov | 事实标准，mock fixture 丰富 |
| 分发 | Docker + PyPI | 覆盖容器和开发者两种场景 |
| 配置 | YAML (`pyyaml`) | 人类可读，声明式 |

---

## 9. 验收标准

1. 主循环可运行：输入 coding 任务 → agent 产生动作 → 多轮闭环
2. 六维度机制全部可运行：工具、护栏、反馈、记忆、配置、凭据
3. Mock LLM 测试通过：替换真实 LLM 后，每个核心机制可用确定性单元测试验证
4. 机制演示可复现：① 护栏拦截危险命令 ② 注入失败 → 反馈 → 修正 ③ 反馈分类逻辑
5. `make test` 一键运行全部测试，通过
6. API key 安全存储：首次引导录入 + keyring 存储 + 不回显明文
7. Docker 镜像可构建、PyPI 包可安装
8. CI 配置且最后一次执行 pass

---

## 10. 风险与未决问题

- **JSON 解析稳定性**：DeepSeek 可能返回非标准 JSON → 需健壮的解析 + retry 机制
- **反馈分类准确性**：不同语言/框架的测试输出格式不同 → 先只支持 Python/pytest，后续可扩展
- **HITL 阻塞体验**：CLI 交互中频繁暂停影响体验 → 白名单机制让用户预授权常见安全操作
- **记忆检索质量**：SQLite 关键词匹配可能不够准 → 向量检索作为可选增强

---

## 11. 领域与机制设计

### 反馈信号（Coding 领域）
- 确定性信号：pytest 通过/失败、flake8 错误、命令退出码
- 非确定性信号（不作依赖）：LLM 自评
- 原则：所有回灌信号来自工具实际输出

### 危险动作（Coding 领域）
- 文件级：`rm -rf`、覆盖系统目录、删除 `.git/`
- 命令级：`sudo`、`chmod 777`、`git push --force`、写入 `/dev/`
- 判定方式：正则匹配 + 路径范围检查

### 所需工具
`read_file`、`write_file`、`run_shell`、`run_test`

### 记忆需求
项目约定、用户偏好、历史决策

### 重点维度：反馈闭环
理由：coding 场景下"跑测试看结果"是唯一客观、确定、可自动化的质量信号，天然闭环——失败 → 分析 → 修正 → 再跑。所有机制为代码实现：FeedbackCollector 是确定性校验器，不依赖 LLM 判断。

### 机制编码实现
- 反馈信号 = 编写的校验器（解析产物 → 客观判定 → 回灌），不是提示词
- 危险动作 = 编写的护栏函数（识别 → 拦截 → HITL），不是提示词
- 移除真实 LLM 后，每个机制仍是可单测的确定性代码
