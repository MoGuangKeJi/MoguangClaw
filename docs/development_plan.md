# MoguangClaw 开发计划

> 基于 [architecture.md](./architecture.md) v0.4 制定，按 Phase 划分，每个任务标注依赖关系与验收标准。

---

## Phase 1：核心 Agent 能力（MVP）

> **目标**: 在终端里跑通完整的 Agent 对话循环 —— 用户输入任务 → LLM 思考 → 调用工具 → 返回结果。
>
> **预计工期**: 2 周

### 1.1 项目骨架搭建

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 1.1.1 | 初始化项目目录结构 | `src/moguangclaw/` 全部子目录及 `__init__.py` | 无 | `python -c "import moguangclaw"` 不报错 |
| 1.1.2 | 创建 `requirements.txt` | `requirements.txt` | 无 | `pip install -r requirements.txt` 成功 |
| 1.1.3 | 实现配置加载 | `src/moguangclaw/config.py`, `config.yaml` | 无 | 能从 YAML 读取 LLM API Key、模型名称等配置 |
| 1.1.4 | 创建 Workspace 初始模板 | `workspace/AGENTS.md`, `SOUL.md`, `MEMORY.md` | 无 | 文件内容包含初版系统提示词 |
| 1.1.5 | 实现首次启动 Workspace 初始化逻辑 | `config.py` 中增加检测与拷贝 | 1.1.3, 1.1.4 | 首次运行自动将 `workspace/` 拷贝到 `~/.moguangclaw/workspace/` |

### 1.2 LLM Provider

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 1.2.1 | 定义 Provider 基类与数据模型 | `src/moguangclaw/llm/base.py` | 1.1.1 | `BaseLLMProvider`、`LLMResponse`、`ToolCall` 数据类定义完成 |
| 1.2.2 | 实现 Qianwen Provider | `src/moguangclaw/llm/qianwen.py` | 1.2.1, 1.1.3 | 能调用千问模型完成单轮对话（含 Function Calling），支持流式输出 |
| 1.2.3 | 实现 OpenAI Provider | `src/moguangclaw/llm/openai_provider.py` | 1.2.1, 1.1.3 | 能调用 OpenAI 完成单轮对话（含 Function Calling），支持流式输出 |
| 1.2.4 | 编写 LLM Provider 单元测试 | `tests/test_llm.py` | 1.2.2, 1.2.3 | Mock 测试通过，验证请求/响应格式正确 |

### 1.3 工具引擎

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 1.3.1 | 定义 Tool 基类与注册机制 | `src/moguangclaw/tools/base.py`, `registry.py` | 1.1.1 | 工具能自动注册并生成 LLM Function Calling 格式的 JSON Schema |
| 1.3.2 | 实现 `bash` 工具 | `src/moguangclaw/tools/bash.py` | 1.3.1 | 能执行 shell 命令、返回 stdout/stderr、支持超时、命令黑名单拦截 |
| 1.3.3 | 实现文件操作工具 | `src/moguangclaw/tools/file_ops.py` | 1.3.1 | `read_file`、`write_file`、`edit_file`、`list_dir` 功能正常，路径沙箱限制生效 |
| 1.3.4 | 自动生成 `TOOLS.md` | `registry.py` 中增加导出功能 | 1.3.1 | 运行后在 Workspace 生成可读的工具说明文档 |
| 1.3.5 | 编写工具单元测试 | `tests/test_tools.py` | 1.3.2, 1.3.3 | 测试覆盖正常执行、超时、路径越权、命令拦截等场景 |

### 1.4 Agentic Loop（ReAct 循环）

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 1.4.1 | 实现 ReAct 循环核心逻辑 | `src/moguangclaw/agent/loop.py` | 1.2.1, 1.3.1 | LLM 调用 → 解析工具调用 → 执行工具 → 回传结果 → 继续循环，直到文本回复或达到 max_turns |
| 1.4.2 | 实现上下文组装 | `src/moguangclaw/agent/context.py` | 1.4.1 | 正确拼装 System Prompt + MEMORY.md + 每日日志 + 会话历史 + 用户消息 |
| 1.4.3 | 实现滑动窗口记忆 | `src/moguangclaw/memory/store.py`, `context_builder.py` | 1.4.2 | 会话历史超过 N 轮时自动截断旧消息，N 可配置 |

### 1.5 CLI Channel + 入口

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 1.5.1 | 定义 Channel 基类 | `src/moguangclaw/channels/base.py` | 1.1.1 | 定义 `BaseChannel`、`IncomingMessage`、`OutgoingMessage` |
| 1.5.2 | 实现 CLI Channel | `src/moguangclaw/channels/cli.py` | 1.5.1 | 终端交互式对话，使用 rich 美化输出（Markdown 渲染、代码高亮） |
| 1.5.3 | 实现程序入口 | `src/moguangclaw/main.py` | 1.5.2, 1.4.1, 1.2.2, 1.3.1, 1.1.3 | `python -m moguangclaw.main` 启动后可在终端与 Agent 持续对话 |

### Phase 1 里程碑验收

```
用户在终端输入: "帮我在当前目录创建一个 hello.py，内容是打印 hello world，然后运行它"

预期 Agent 行为:
  1. 调用 write_file 创建 hello.py
  2. 调用 bash 执行 python hello.py
  3. 返回执行结果 "hello world"
```

---

## Phase 2：钉钉接入 + 记忆增强

> **目标**: 通过钉钉与 Agent 对话，支持多会话和上下文裁剪。
>
> **预计工期**: 2 周
>
> **前置**: Phase 1 全部完成

### 2.1 Gateway Server

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 2.1.1 | 实现 Gateway HTTP 服务 | `src/moguangclaw/gateway/server.py` | Phase 1 | asyncio HTTP 服务启动，`/health` 返回 200 |
| 2.1.2 | 实现会话管理 | `src/moguangclaw/gateway/session.py` | 2.1.1 | 按 sender_id 创建/复用独立会话，会话有独立上下文和历史 |
| 2.1.3 | 实现消息队列 | `server.py` 中增加 | 2.1.2 | 同一会话的并发消息按序处理，不产生竞态 |

### 2.2 钉钉 Channel

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 2.2.1 | 实现钉钉 Channel Adapter | `src/moguangclaw/channels/dingtalk.py` | 2.1.1, 1.5.1 | 通过 `dingtalk-stream` 接收钉钉消息，标准化为 `IncomingMessage` |
| 2.2.2 | 实现消息回复 | `dingtalk.py` | 2.2.1 | Agent 回复能推送回钉钉对话（支持 Markdown 格式） |
| 2.2.3 | 实现钉钉机器人创建指南 | `docs/dingtalk_setup.md` | 无 | 文档说明如何在钉钉开放平台创建机器人并获取 AppKey/AppSecret |

### 2.3 Session Pruning

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 2.3.1 | 实现 Pruning 引擎 | `src/moguangclaw/memory/pruner.py` | 1.4.2 | 按互斥优先级链执行：豁免 → Hard Clear → Soft Trim → 保留 |
| 2.3.2 | 集成到 Agentic Loop | `context.py` 修改 | 2.3.1 | 每次 LLM 调用前自动裁剪内存副本，不影响磁盘 `.jsonl` |
| 2.3.3 | 编写 Pruning 单元测试 | `tests/test_pruner.py` | 2.3.1 | 覆盖各优先级分支、边界条件、保护规则和豁免规则 |

### 2.4 心跳调度器

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 2.4.1 | 实现 Heartbeat 调度 | `src/moguangclaw/gateway/heartbeat.py` | 2.1.1 | 按配置间隔唤醒 Agent，读取 `HEARTBEAT.md` 并决定是否执行 |

### Phase 2 里程碑验收

```
用户在钉钉中对 MoguangClaw 机器人发消息: "查看当前服务器磁盘使用情况"

预期行为:
  1. 钉钉消息 → Gateway → Agent Runner → Agentic Loop
  2. Agent 调用 bash("df -h")
  3. 结果通过钉钉消息推送回用户
  4. 在同一对话中继续追问可保持上下文
```

---

## Phase 3：生产化

> **目标**: 具备在云端长期稳定运行的能力。
>
> **预计工期**: 2 周
>
> **前置**: Phase 2 全部完成

### 3.1 Compaction + 长期记忆

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 3.1.1 | 实现 Memory Flush | `src/moguangclaw/memory/compactor.py` | Phase 2 | 触发阈值时静默提示 Agent 写入关键记忆到 `MEMORY.md` |
| 3.1.2 | 实现 Compaction 摘要压缩 | `compactor.py` | 3.1.1 | 旧对话由 LLM 摘要化 → 写回 `.jsonl`（持久化，不可逆） |
| 3.1.3 | 编写 Compaction 测试 | `tests/test_compactor.py` | 3.1.2 | 验证摘要生成、文件重写、Token 预估准确性 |

### 3.2 模型 Failover

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 3.2.1 | 实现 Failover 机制 | `src/moguangclaw/llm/base.py` 修改 | Phase 1 | 主模型（Qianwen）调用失败时自动切换 OpenAI，并记录错误日志 |

### 3.3 安全与审计

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 3.3.1 | 实现审计日志 | `src/moguangclaw/tools/base.py` 修改 | 1.3.1 | 所有工具调用写入 `~/.moguangclaw/logs/tool_audit.jsonl` |
| 3.3.2 | 实现人工确认模式 | `bash.py` + `dingtalk.py` 联动 | 2.2.2, 1.3.2 | `confirmMode: "dangerous"` 时高危命令暂停并通过钉钉询问用户 |

### 3.4 Docker 打包部署

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 3.4.1 | 编写 Dockerfile | `Dockerfile` | Phase 2 | `PYTHONPATH` 正确设置，镜像启动后 `/health` 返回 200 |
| 3.4.2 | 编写 docker-compose.yml | `docker-compose.yml` | 3.4.1 | `docker compose up` 后 Agent 自动连接钉钉并响应消息 |
| 3.4.3 | 验证跨平台构建 | 无 | 3.4.1 | M2 Mac 上通过 buildx 构建 `linux/amd64` 镜像，在 x86 Linux 容器中正常运行 |
| 3.4.4 | 编写部署文档 | `docs/deployment.md` | 3.4.3 | 从零到上线的完整操作步骤 |

### 3.5 日志与监控

| # | 任务 | 产出文件 | 依赖 | 验收标准 |
|---|------|---------|------|---------|
| 3.5.1 | 结构化日志 | `src/moguangclaw/` 各模块 | Phase 2 | 使用 Python `logging` + JSON 格式输出到 stdout（便于 Docker 采集） |
| 3.5.2 | 错误告警 | `gateway/server.py` | 3.5.1, 2.2.2 | Agent 执行异常时通过钉钉通知管理员 |

### Phase 3 里程碑验收

```
1. 在 M2 Mac 上执行 docker buildx build --platform linux/amd64，镜像构建成功
2. 镜像推送到仓库后，在 x86 Linux 服务器上 docker compose up
3. 通过钉钉发送消息，Agent 正常响应
4. 超长对话自动触发 Compaction，旧历史被摘要化
5. 执行 rm -rf / 被命令黑名单拦截
```

---

## 任务依赖总览

```
Phase 1 (MVP)
  1.1 骨架 ─┬─ 1.2 LLM Provider ──┐
            ├─ 1.3 工具引擎 ───────┤
            └─ 1.5 CLI Channel ────┼─ 1.4 Agentic Loop ── ✅ MVP 完成
                                   │
Phase 2 (钉钉 + 裁剪)              │
  2.1 Gateway ─┬─ 2.2 钉钉 ───────┤
               ├─ 2.3 Pruning ────┤
               └─ 2.4 心跳 ───────┼── ✅ Phase 2 完成
                                   │
Phase 3 (生产化)                    │
  3.1 Compaction ──────────────────┤
  3.2 Failover ────────────────────┤
  3.3 安全审计 ────────────────────┤
  3.4 Docker 部署 ─────────────────┤
  3.5 日志监控 ────────────────────┼── ✅ Phase 3 完成
```

---

## 开发约定

- **分支策略**: `main`（稳定）← `dev`（开发）← `feature/*`（功能分支）
- **测试要求**: 每个模块完成后编写单元测试，Phase 里程碑验收前通过全部测试
- **文档同步**: 代码变更涉及架构调整时同步更新 `docs/architecture.md`
- **Commit 规范**: `feat:` / `fix:` / `docs:` / `test:` / `chore:` 前缀
