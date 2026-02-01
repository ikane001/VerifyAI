# VerifyAI

**AI驱动的自动化验证系统** - 让代码质量保障从繁琐变简单

[![PyPI version](https://img.shields.io/pypi/v/verify-ai.svg)](https://pypi.org/project/verify-ai/)
[![Tests](https://img.shields.io/badge/tests-105%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 为什么需要 VerifyAI？

在快速迭代的 AI 时代，代码变更频繁，传统的测试维护方式已经跟不上节奏：

| 传统方式的痛点 | VerifyAI 的解决方案 |
|---------------|-------------------|
| 手写测试耗时费力 | LLM 自动生成高质量测试 |
| 测试覆盖不全面 | 智能分析代码结构，全面覆盖 |
| 测试失败难定位 | AI 分析根因，自动建议修复 |
| 回归测试慢 | 增量验证，只测变更相关 |
| 多语言项目难统一 | 统一支持 Python/JS/TS/Go/Java |

---

## 核心价值

### 🚀 一键初始化，零配置启动

```bash
# 安装
pip install verify-ai

# 初始化（自动检测项目结构）
vai init

# 生成测试
vai generate

# 就这么简单！
```

### 🧠 智能测试生成

- **理解代码语义**：不是简单的模板填充，而是真正理解函数逻辑
- **覆盖边界情况**：自动发现潜在的边界条件和异常情况
- **支持多LLM**：Claude、OpenAI、Ollama 本地模型均可

### ⚡ 增量验证，极速反馈

```bash
# 只验证本次变更影响的代码
vai verify --trigger push     # 2分钟快速检查
vai verify --trigger pr       # 5分钟标准检查
vai verify --trigger merge    # 10分钟完整检查
```

### 🔧 智能问题分析

```bash
# 测试失败？让 AI 帮你分析
vai analyze

# 自动识别：
# - 根本原因
# - 问题位置
# - 修复建议
```

---

## 快速开始

### 安装

```bash
# 方式一：从 PyPI 安装（推荐）
pip install verify-ai

# 方式二：完整安装（包含服务器、Dashboard 功能）
pip install 'verify-ai[all]'

# 方式三：从源码安装（开发模式）
git clone https://github.com/ikane001/VerifyAI.git
cd VerifyAI
pip install -e '.[dev]'
```

### 三步上手

```bash
# 1️⃣ 初始化项目
cd your-project
vai init

# 2️⃣ 扫描项目结构
vai scan --verbose

# 3️⃣ 生成测试
vai generate --dry-run  # 预览
vai generate            # 执行
```

### 日常使用

```bash
# 提交前快速验证
vai verify --trigger push

# PR 检查
vai verify --trigger pr --base main

# 查看变更
vai diff --from HEAD~3 --to HEAD

# 分析测试失败
vai analyze --output pytest_output.txt

# 覆盖率分析
vai coverage --threshold 80

# 启动 Dashboard
vai dashboard
```

---

## 完整命令参考

| 命令 | 功能 | 示例 |
|------|------|------|
| `vai init` | 初始化项目配置 | `vai init .` |
| `vai scan` | 扫描项目结构 | `vai scan --verbose` |
| `vai generate` | 生成测试 | `vai generate --type unit` |
| `vai verify` | 运行验证 | `vai verify --trigger pr` |
| `vai diff` | 查看Git变更 | `vai diff --from HEAD~1` |
| `vai commits` | 提交历史 | `vai commits -n 10` |
| `vai analyze` | 分析失败 | `vai analyze --fix` |
| `vai replay` | 从日志生成测试 | `vai replay api.har` |
| `vai coverage` | 覆盖率分析 | `vai coverage --threshold 80` |
| `vai dashboard` | 启动Web仪表盘 | `vai dashboard --port 8080` |
| `vai server` | 启动API服务 | `vai server -p 8000` |

---

## 分层验证策略

VerifyAI 根据不同场景自动选择最优策略：

```
┌─────────────┬──────────────┬─────────────┬─────────────────────┐
│   触发时机   │    超时时间   │   测试范围   │      特点           │
├─────────────┼──────────────┼─────────────┼─────────────────────┤
│ push        │    2分钟     │  变更文件    │ 快速反馈，不阻塞     │
│ PR          │    5分钟     │  变更+影响   │ 生成缺失测试         │
│ merge       │   10分钟     │  全量回归    │ 阻塞不合格代码       │
│ scheduled   │    1小时     │  全项目      │ 重新生成过时测试     │
└─────────────┴──────────────┴─────────────┴─────────────────────┘
```

---

## 支持的语言

使用 tree-sitter 进行多语言 AST 解析：

- ✅ Python - 完整支持
- ✅ JavaScript/TypeScript - 完整支持
- ✅ Go - 完整支持
- ✅ Java - 完整支持

---

## 集成方式

### 1. CLI 工具（推荐新手）

```bash
vai generate
vai verify
```

### 2. Cursor Skill（IDE 集成）

项目包含 `SKILL.md`，Cursor AI 可直接调用 VerifyAI 功能。

### 3. MCP Server（AI 助手集成）

```bash
vai mcp-server
```

支持 Claude Desktop、Cursor 等 MCP 兼容的 AI 工具。

### 4. REST API（团队服务）

```bash
vai server --port 8000
```

提供完整的 REST API，支持 GitHub Webhook 自动触发。

### 5. GitHub Actions

```yaml
# .github/workflows/verify.yml
- name: Run VerifyAI
  run: |
    pip install verify-ai
    vai verify --trigger pr
```

---

## 场景还原

从真实日志生成测试，覆盖实际使用场景：

```bash
# 从浏览器录制生成测试
vai replay session.har --output tests/test_browser.py

# 从 API 日志生成测试
vai replay nginx_access.log --output tests/test_api.py

# 从错误日志生成复现测试
vai replay error.log --format error
```

---

## 配置文件

`verify-ai.yaml` 示例：

```yaml
project:
  name: my-project
  languages: [python, typescript]
  test_output: ./tests/generated

llm:
  provider: claude           # claude | openai | ollama
  model: claude-sonnet-4-20250514
  fallback: ollama/codellama # 本地备选

triggers:
  push: [lint, affected_unit_tests]
  pull_request: [unit_tests, integration_tests, ai_review]
  merge_to_main: [regression_tests, e2e_tests]

fix:
  auto_fix_tests: true       # 自动修复测试代码
  auto_fix_source: false     # 源码修复需确认
  require_approval: true
```

---

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `VAI_CLAUDE_API_KEY` | Claude API Key |
| `VAI_OPENAI_API_KEY` | OpenAI API Key |
| `GITHUB_TOKEN` | GitHub Token（服务器模式） |
| `GITHUB_WEBHOOK_SECRET` | Webhook 签名密钥 |

> 💡 如果已安装 Claude Code，会自动读取 `~/.claude/settings.json` 中的配置。

---

## 项目架构

```
verify-ai/
├── src/verify_ai/
│   ├── core/           # 核心引擎（扫描、生成）
│   ├── parsers/        # 代码解析（AST、OpenAPI）
│   ├── llm/            # LLM 客户端（Claude/OpenAI/Ollama）
│   ├── git/            # Git 集成（追踪、策略）
│   ├── analysis/       # 失败分析与修复
│   ├── scenario/       # 场景还原
│   ├── coverage/       # 覆盖率分析
│   ├── dashboard/      # Web Dashboard
│   ├── mcp/            # MCP Server
│   └── server/         # REST API
├── tests/              # 测试套件
├── examples/           # 示例项目
└── SKILL.md            # Cursor Skill 配置
```

---

## 开发

```bash
# 克隆项目
git clone https://github.com/ikane001/VerifyAI.git
cd VerifyAI

# 安装开发依赖
pip install -e '.[dev]'

# 运行测试
pytest tests/ -v

# 代码检查
ruff check src/
```

---

## 路线图

- [x] Phase 1: 核心引擎 + 多LLM支持
- [x] Phase 2: tree-sitter 多语言解析
- [x] Phase 3: Git 增量追踪
- [x] Phase 4: 智能问题分析
- [x] Phase 5: 场景还原
- [x] Phase 6: Cursor Skill + MCP
- [x] Phase 7: GitHub Webhook + API
- [x] Phase 8: Web Dashboard
- [x] Phase 9: 覆盖率分析
- [ ] Phase 10: 性能测试生成

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

## License

MIT License
