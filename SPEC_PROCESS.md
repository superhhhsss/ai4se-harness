# SPEC_PROCESS.md — 冷启动验证记录

## 验证方式

使用当前 Claude Code（DeepSeek v4 pro）作为"陌生 agent"，仅提供 `SPEC.md` + `PLAN.md`，不提供任何口头解释，模拟一个全新 agent 按 PLAN 实现 Task 1 和 Task 2。

## 关键发现

### 发现 1：`build-backend` 写错（致命）

**位置**：PLAN.md Task 1 Step 1, pyproject.toml

**错误**：`build-backend = "setuptools.backends._legacy:_Backend"`

**正确**：`build-backend = "setuptools.build_meta"`

**影响**：`pip install -e .` 直接报 `ModuleNotFoundError: No module named 'setuptools.backends'`，陌生 agent 会在第一步就卡住，无法继续。

**原因**：PLAN 中写了一个不存在的模块路径。正确的 setuptools PEP 517 后端是 `setuptools.build_meta`。

### 发现 2：缺少 `make` 的替代方案说明（中等）

**位置**：PLAN.md Task 1 Step 2, Makefile

**问题**：PLAN 定义了 `make test`、`make install` 等命令，但 Windows 默认没有 `make`。陌生 agent 在 Windows 上执行 `make test` 会得到 `command not found`。

**建议**：在 PLAN 头部或 README 中说明 Windows 用户可用 `pytest tests/ -v` 替代 `make test`，或提供 `python -m pytest tests/ -v` 作为跨平台方案。

### 发现 3：测试步骤缺少 dev 依赖安装（中等）

**位置**：PLAN.md 多个 Task 的测试运行步骤

**问题**：所有 Task 的测试运行步骤都直接写 `pytest tests/test_xxx.py -v`，但 Task 1 的 `pip install -e .` 只装了核心依赖，不装 pytest。如果陌生 agent 的环境没有全局安装 pytest，测试会失败。

**建议**：在 Task 1 末尾增加一步 `pip install -e ".[dev]"`，或在每个 Task 的测试步骤前加一条检查。

### 发现 4：子目录创建未提前说明（轻微）

**位置**：PLAN.md Task 5, Task 8

**问题**：Task 5 需要创建 `src/ai4se_harness/llm/`，Task 8 需要创建 `src/ai4se_harness/tools/`。PLAN 在 Task 1 只创建了 `src/ai4se_harness/` 和 `tests/` 根目录，子目录的 `__init__.py` 要到对应 Task 才创建。陌生 agent 可能因为父目录不存在而报错。

**建议**：在 Task 5 和 Task 8 的 Step 中显式加入 `mkdir -p` 命令。

### 发现 5：SPEC 和 PLAN 整体质量评估

**做得好的：**
- 数据模型清晰，Task 2 完全按 PLAN 执行零问题
- TDD 流程（红→绿→重构→提交）每一步都有明确命令和预期输出
- 依赖关系图让陌生 agent 可以理解执行顺序

**需要改进的：**
- 脚手架阶段（Task 1）的 build-backend 错误是硬 bug
- 缺少平台兼容性说明（Windows vs Linux）
- 部分 Step 合并了"运行失败"和"编写代码"两步（如 Task 7 "Run to verify fail, then write parser.py"），实际上应该是两个独立 step

## 对 SPEC/PLAN 的修订

1. **修复 pyproject.toml 的 build-backend**（已当场修复）
2. **PLAN.md 中修复 build-backend 字符串**
3. **Task 1 增加 dev 依赖安装步骤**
4. **在 PLAN 头部添加平台兼容性说明**