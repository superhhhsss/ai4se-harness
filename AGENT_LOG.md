# AGENT_LOG.md

按时间顺序记录关键开发节点。

---

## 2026-07-07

### 15:00 — 项目初始化

- **触发技能**: 无（手动初始化）
- **操作**: 初始化 git 仓库，创建 GitHub 公开仓库 `superhhhsss/ai4se-harness`
- **提交**: `858fc90` — Initial commit（.gitignore）
- **教训**: 无

### 15:30 — 需求分析

- **触发技能**: brainstorming（Superpowers）
- **操作**: 阅读两份需求文档，逐项确认技术选型
- **关键决策**: Python 语言、反馈闭环重点维度、DeepSeek LLM、Docker+PyPI 分发、CLI 交互式、标准工具集
- **教训**: brainstorming 的逐项确认流程避免了"先入为主"的选型——比如最初想选 Go，但讨论后认识到 Python 的 mock 和 keyring 生态更适合这个项目

### 16:00 — SPEC 编写

- **触发技能**: brainstorming（继续）
- **操作**: 确认管道架构（方案 A）、7 阶段 + 3 侧通道设计，沉淀为 SPEC.md（11 章节）
- **提交**: `27f81e4` — SPEC.md
- **教训**: 管道架构 vs 状态机架构的讨论很有价值，最终选择管道是因为"所有成熟 agent 框架都用管道模式"，这个工程常识比"作业提到了状态机"更重要

### 16:30 — PLAN 编写

- **触发技能**: writing-plans
- **操作**: 将 SPEC 分解为 18 个 task，每 task 包含 TDD 步骤（红→绿→重构→提交）
- **提交**: `fae8e01` — PLAN.md（第一版）
- **教训**: 写 PLAN 时发现 FeedbackCollector 的 mock 私有方法设计不够干净，在 PLAN 阶段就改成了构造注入。这个前置修正节省了实现阶段的重构成本

---

## 2026-07-08

### 10:00 — PLAN 修订

- **触发技能**: writing-plans（修订）
- **操作**: 将 PLAN 非代码部分改为中文，修复 build-backend 错误，FeedbackCollector 改为构造注入，去掉 `/tmp/` 硬编码
- **提交**: `31902ce` — PLAN.md 修订版
- **教训**: 用户反馈"PLAN 非代码部分应该是中文"提醒了我——文档语言应与项目语境一致

### 10:30 — 冷启动验证

- **触发技能**: 无（手动模拟 Codex CLI 作为第二 agent）
- **操作**: 仅凭 SPEC.md + PLAN.md 实现 Task 1 和 Task 2（脚手架 + 数据模型）
- **发现**: 4 个问题——build-backend 写错（致命）、缺少 dev 依赖安装（中等）、子目录未预创建（轻微）、缺少平台兼容性说明（轻微）
- **提交**: `d8a5fb9` — 冷启动修复 + `a62304e` — SPEC_PROCESS.md
- **教训**: 冷启动验证是本次项目最有价值的质量保障步骤。build-backend 错误如果不在这里发现，会在 CI 或别的开发者机器上才暴露，修复成本高得多

### 10:45 — 正式开始实现

- **触发技能**: subagent-driven-development（串行模式）
- **操作**: 按依赖关系逐个推进 task

### 10:45-11:00 — Tasks 3+4: 配置 + 凭据

- **提交**: `05d90c0` — 配置模块 + 凭据管理器
- **测试**: 8/8 pass
- **问题**: `test_get_returns_none_when_not_set` 因为真实环境变量 `DEEPSEEK_API_KEY` 存在而失败，需要同时 mock `os.getenv`。这暴露了 fallback 设计的一个实际问题：keyring 和 env 的优先级需要明确文档化

### 11:00-11:15 — Tasks 5,6,7,10,12: LLM + 记忆 + 解析器 + 护栏 + 停机

- **提交**: `0eb0a16` — 五个模块并行实现
- **测试**: 25/25 pass（3 个初始失败后修复）
- **问题**:
  1. Memory 检索 `LIKE %python style%` 匹配不到 `python_style`，因为空格和下划线不同
  2. Parser 对缺少 `tool` 字段的 JSON 默认返回 `stop` 而非报错，与测试预期不符
  3. StopJudge 的停滞检测只在 feedback 失败时触发，应该无论 feedback 状态都检查
- **人工干预**: 全部当场修复

### 11:15-11:25 — Tasks 8,9,11: 工具系统 + 反馈收集器 ★

- **提交**: `6433acf` — 工具注册表 + 4 个内置工具 + 反馈收集器
- **测试**: 17/17 pass（5 tools + 12 feedback）
- **重点维度**: FeedbackCollector 实现完成——构造注入、编译/测试/lint 三级分类、自修正轮数跟踪、lint 输出解析
- **教训**: 反馈收集器的 12 个测试中，最有用的是"截断长报告"和"非 Python 文件跳过"这两个边缘测试，它们在实际使用中会经常触发

### 11:25-11:35 — Tasks 13,14: 上下文构建器 + 主循环

- **提交**: `516450b` — 上下文构建器 + 主循环
- **测试**: 6/6 pass（2 个初始失败后修复）
- **问题**:
  1. Windows 路径反斜杠在 JSON 中非法，需要用 `as_posix()` 转换
  2. 护栏的 workspace 默认为 `os.getcwd()`，导致写 `tmp_path` 被拦截。通过给 Harness 添加 `workspace` 参数解决
- **人工干预**: 修正测试中的路径处理和 Harness 的 workspace 支持

### 11:35-11:45 — Tasks 15-18: CLI + Demo + Docker + CI + README

- **提交**: `f24d81d` — 最终交付
- **测试**: 全部 65/65 pass
- **操作**: CLI 入口（click）、机制演示 3 个场景、Dockerfile、CI config、README

---

## 统计

- **总提交**: 8 次
- **总测试**: 65 个
- **总文件**: 26 源码 + 14 测试
- **人工干预**: 6 次（build-backend 修正、env fallback mock、LIKE 查询修正、parser 验证增强、路径处理、workspace 参数）
- **关键教训**: TDD 在 AI 协作中是放大器——mock LLM 让所有机制可脱离真实 API 快速验证；冷启动验证是 SPEC/PLAN 质量的最有效反馈机制