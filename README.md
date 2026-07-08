# AI4SE Coding Agent Harness

CLI 交互式 Coding Agent Harness，采用管道架构。Agent = LLM + Harness。
所有机制（护栏、反馈、记忆）均为代码实现，不是提示词。

## 快速开始

```bash
pip install -e .
ai4se-harness key setup    # 安全录入 DeepSeek API key
ai4se-harness run          # 启动 agent
```

### Docker

```bash
docker build -t ai4se-harness .
docker run -it -e DEEPSEEK_API_KEY=sk-xxx ai4se-harness run
```

## Key 管理

API key 存储在操作系统钥匙串中，绝不硬编码、不提交 Git。

- `ai4se-harness key setup` — 安全录入
- `ai4se-harness key status` — 查看状态（不回显明文）
- `ai4se-harness key clear` — 删除

环境变量 fallback: `DEEPSEEK_API_KEY`（不推荐明文）。

## 架构

7 阶段管道: Context Builder → LLM Call → Action Parser → Guardrail (HITL) → Tool Dispatch → Feedback Collector → Stop Judge

3 个侧通道: Memory (SQLite), Config (YAML), Credentials (keyring)

主要贡献: 反馈收集器 — 确定性测试/lint 结果解析 + 失败分类 (compile vs test vs lint) + 构造注入设计。

## 开发

```bash
make install    # pip install -e .
make test       # 运行全部测试
make lint       # flake8
make cov        # 覆盖率报告
make demo       # 机制演示测试
```

## 目录结构

```
src/ai4se_harness/    — harness 源码
tests/               — 测试套件 (mock LLM, 确定性)
config.yaml          — 默认配置
```

## 已知限制

- 仅支持 Python 项目测试 (pytest/flake8)
- 单一 LLM 后端 (DeepSeek)；扩展只需实现 LLMBackend
- 不支持流式响应
- 文件写入限制在工作区目录内

## 安全

- API key: 系统钥匙串 (主) 或环境变量 (fallback)
- Shell: 基于正则的危险命令检测
- 文件 IO: 工作区边界强制
- 日志/终端/历史记录中不出现凭据