# MoguangClaw 架构设计文档 v0.4

> 简化版 OpenClaw —— 基于通义千问 (Qianwen) 与 OpenAI 的个人 AI 智能助手

## 1. 项目概述

**OpenClaw** 是一个自托管的个人 AI 助手框架，在本地运行 Gateway 网关进程，通过通讯软件交互，底层 AI 模型以 ReAct 循环自主完成任务。

**MoguangClaw** 的目标是实现 OpenClaw 的**核心子集**，用 Python 重写，模型层使用通义千问 (Qianwen) Code/Plan，并兼容 OpenAI API。

### 1.1 简化范围

| OpenClaw 完整功能 | MoguangClaw 目标 |
|---|---|
| 20+ 通讯渠道 | **CLI（开发调试）+ 钉钉（生产）** |
| Node.js | **Python 3.13** |
| Claude/GPT/Gemini/Ollama 多模型 | **Qianwen Code/Plan（主力）+ OpenAI（备选）** |
| 浏览器控制、Canvas、语音唤醒 | 初期不做 |
| macOS/iOS/Android 原生 App | 不做 |
| 完整 Skill 生态 | 基础技能加载 |
| Docker 沙箱执行 | 本地 Workspace 目录隔离 |
| 心跳调度器 | 简化版定时任务 |

---

## 2. 系统架构总览

```
用户 (钉钉 / CLI)
        │
        ▼
┌─────────────────────────┐
│   Channel Adapter       │  ← 消息渠道适配层
│   (消息标准化)            │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Gateway Server        │  ← 网关服务（控制面）
│   (会话路由 + 消息队列)   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Agent Runner          │  ← Agent 运行器
│   (上下文组装 + 记忆加载) │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Agentic Loop (ReAct)  │  ← 核心推理-行动循环
│   LLM ⇄ Tool Executor   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Tool / Skill Engine   │  ← 工具执行引擎
│   (bash, file, web...)  │
└─────────────────────────┘
```

---

## 3. 核心模块详解

### 3.1 Channel Adapter（消息渠道适配层）

**职责**: 将不同平台的消息标准化为内部统一格式。

**支持的渠道**:
- **CLI**: 命令行交互，用于开发调试
- **钉钉 (DingTalk)**: 使用钉钉官方 `dingtalk-stream` SDK，通过 Stream 模式接收消息事件，作为生产环境的唯一通讯渠道

**统一消息格式**:
```python
@dataclass
class IncomingMessage:
    channel: str         # "cli" | "dingtalk"
    sender_id: str       # 发送者唯一标识
    session_id: str      # 会话 ID
    content: str         # 消息文本
    attachments: list    # 附件
    timestamp: datetime
```

---

### 3.2 Gateway Server（网关服务）

**职责**: 系统中枢，负责会话管理、消息路由、消息队列和心跳调度。

基于 `asyncio` 事件驱动架构，单进程 + 协程。

**对外服务端口 (HTTP :8080)**:
- `/health` — 健康检查（供 Docker / 负载均衡器探活）
- `/webhook/dingtalk` — 钉钉回调备用入口（主通道为 Stream 长连接，Webhook 作为降级备选）
- 此端口**不承载用户消息流**，用户与 Agent 的交互始终通过钉钉 Stream 完成

---

### 3.3 Agent Runner（Agent 运行器）

**职责**: 接到消息后完成执行前准备：加载记忆 → 组装上下文 → 启动 Agentic Loop。

**Workspace 结构** (仿照 OpenClaw):

> **路径约定**：运行时 Workspace 统一位于 `~/.moguangclaw/workspace/`。仓库中的 `workspace/` 目录是初始模板，首次启动时自动拷贝到运行时路径。代码和文档中所有 `workspace/skills/...` 的引用均指运行时路径 `~/.moguangclaw/workspace/skills/...`。

```
~/.moguangclaw/workspace/          ← 运行时路径（唯一真实路径）
├── AGENTS.md              # Agent 行为与人设指令
├── SOUL.md                # 系统级提示词
├── TOOLS.md               # 可用工具声明（自动生成）
├── HEARTBEAT.md           # 心跳任务清单
├── MEMORY.md              # 长期持久记忆（重要决策、偏好）
├── memory/                # 每日日志
│   ├── 2026-03-08.md
│   └── 2026-03-09.md
├── skills/                # 技能目录
│   └── <skill_name>/
│       └── SKILL.md
└── sessions/              # 会话历史
    └── <session_id>.jsonl
```

仓库中对应的模板目录：
```
MoguangClaw/workspace/             ← 仓库模板（仅初始化用）
├── AGENTS.md
├── SOUL.md
├── MEMORY.md
└── skills/
```

---

### 3.4 记忆与上下文管理

每轮对话不可能把所有历史全部丢给 LLM，必须在有限的上下文窗口内做取舍。

参考 OpenClaw 的做法，MoguangClaw 的上下文管理分为 **三层策略**，各层**作用域和副作用**明确隔离：

| 层级 | 作用域 | 是否修改磁盘 |
|------|--------|-------------|
| 上下文组装 | 每次 LLM 调用前 | ❌ 只读 |
| Session Pruning | 每次 LLM 调用前 | ❌ 仅修改内存副本 |
| Compaction | 触发阈值时 | ✅ 重写会话文件 |

#### 第一层：上下文组装 — 控制"送什么进去"

每次调用 LLM 时，按以下优先级组装上下文（总 Token 数不超过模型窗口限制）：

```
┌─────────────────────────────────────────────────────┐
│ 1. System Prompt (SOUL.md + AGENTS.md + TOOLS.md)   │  ← 固定，每次都带
│ 2. 长期记忆 (MEMORY.md)                              │  ← 固定，每次都带
│ 3. 今日 + 昨日日志 (memory/YYYY-MM-DD.md)            │  ← 固定，每次都带
│ 4. 当前会话历史 (session history)                     │  ← 最近 N 轮，动态裁剪
│ 5. 当前用户消息                                       │  ← 固定
└─────────────────────────────────────────────────────┘
```

- `MEMORY.md`: 持久化的重要信息（用户偏好、关键决策），由 Agent 主动写入
- `memory/YYYY-MM-DD.md`: 每日追加式日志，只加载今天和昨天的
- 会话历史: 不是全量加载，而是取最近的对话轮次

#### 第二层：Session Pruning（会话裁剪）— 控制"怎么瘦身"

当会话历史过长时，对**工具调用结果 (toolResult)** 进行分级瘦身。

**执行顺序**：按优先级从高到低，**互斥匹配**（命中一条即停止）：

| 优先级 | 策略 | 条件 | 处理方式 |
|--------|------|------|----------|
| 0 (豁免) | **保护** | 最近 3 轮 assistant 消息关联的 toolResult | 跳过，不裁剪 |
| 0 (豁免) | **保护** | 包含图片的 toolResult | 跳过，不裁剪 |
| 1 | **Hard Clear（硬清除）** | toolResult 字符数 ≥ `minPrunableChars × hardClearRatio`（默认 50%） | 整段替换为 `[旧工具结果已清除]` |
| 2 | **Soft Trim（软裁剪）** | toolResult 字符数 ≥ `minPrunableChars × softTrimRatio`（默认 30%） | 保留头尾各 1500 字符，中间用 `...` 替代 |
| - | **保留** | 以上均未命中 | 原样保留 |

> 裁剪**仅作用于发给 LLM 的内存副本**，不修改磁盘上的 `.jsonl` 会话文件。

#### 第三层：Compaction（压缩归档）— 控制"怎么归档"

> ⚠️ **与 Pruning 的区别**: Pruning 是每次请求的瞬时操作，不碰磁盘。Compaction 是**持久化操作**，会重写会话文件 (`.jsonl`)，将旧对话替换为摘要。

当会话 Token 逼近模型上下文窗口限制时：
1. **Memory Flush**: 先触发一次静默的"记忆刷写"，让 Agent 把重要信息写入 `MEMORY.md` 和当日日志
2. **摘要压缩**: 将较旧的对话历史交给 LLM 生成一段摘要
3. **持久化**: 压缩后的摘要**写回会话文件**（`.jsonl`），替代被摘要的原始对话轮次

```
触发条件: 估算 Token 数 > contextWindow - reserveTokensFloor

流程:
  1. 检测当前 token 使用量
  2. 触发 memory flush → Agent 静默写重要记忆到文件
  3. 将老对话摘要化
  4. 摘要写回 .jsonl 会话文件（持久化，不可逆）
  5. 新的一轮调用使用精简后的 history
```

#### 简化版实现方案

在 MoguangClaw 中，我们分阶段实现：

| 阶段 | 实现内容 |
|------|---------|
| **MVP** | 滑动窗口（只保留最近 N 轮完整对话），超出部分直接丢弃 |
| **Phase 2** | 加入 Soft Trim / Hard Clear 裁剪 toolResult |
| **Phase 3** | 加入 Compaction（摘要压缩）和 Memory Flush |
| **未来** | 加入向量记忆搜索（Embedding + 语义检索） |

---

### 3.5 Agentic Loop（ReAct 推理-行动循环）

核心循环，不断 Think → Act → Observe 直到任务完成：

```
1. 组装 Prompt (Context + History)
         │
         ▼
2. 调用 LLM（Qianwen / OpenAI）
         │
         ▼
3. 解析 LLM 响应
    ├─ 文本回复 → 返回用户，循环结束
    └─ 工具调用 → 继续 ↓
         │
         ▼
4. 执行工具，获取 Observation
         │
         ▼
5. 将 Observation 追加到 History → 回到 1
```

- **最大循环次数**: 默认 20 轮
- **流式输出**: 支持 LLM 流式回复
- **工具调用**: 使用模型原生 Function Calling

---

### 3.6 LLM Provider（模型接口层）

```python
class BaseLLMProvider(ABC):
    async def chat(self, messages, tools, stream) -> LLMResponse: ...

class QianwenProvider(BaseLLMProvider):
    """通义千问（主力）- dashscope SDK"""

class OpenAIProvider(BaseLLMProvider):
    """OpenAI（备选/Fallback）- openai SDK"""
```

支持模型 Failover：主模型失败时自动切换到备选。

---

### 3.7 Tool / Skill Engine（工具与技能引擎）

| 工具名 | 功能 |
|--------|------|
| `bash` | 执行 Shell 命令 |
| `read_file` | 读取文件 |
| `write_file` | 写入/创建文件 |
| `edit_file` | 编辑文件 |
| `list_dir` | 浏览目录 |
| `web_search` | 联网搜索（Phase 2） |

技能以 `~/.moguangclaw/workspace/skills/<name>/SKILL.md` 形式加载。

#### 工具安全模型

由于 `bash` 和文件写入工具具有高破坏性，必须在架构层面定义安全边界：

**路径沙箱**:
- 所有文件操作（read/write/edit）限制在 Workspace 根目录 (`~/.moguangclaw/workspace/`) 内
- 路径参数经过标准化后必须以 Workspace 根开头，拒绝 `../` 逃逸
- 可通过配置 `tools.file.allowedPaths` 显式添加额外允许路径

**命令拦截**:
- `bash` 工具维护一份**命令黑名单**，拦截高危操作：
  - 系统级: `rm -rf /`, `mkfs`, `dd`, `shutdown`, `reboot`
  - 网络级: `curl | sh`, `wget -O- | bash` 等管道执行
  - 权限级: `chmod 777`, `chown root`
- 黑名单可通过配置 `tools.bash.denyPatterns` 扩展

**人工确认 (可选)**:
- 配置 `tools.bash.confirmMode: "always" | "dangerous" | "never"`
- `dangerous` 模式下，匹配危险模式的命令会暂停执行，通过钉钉推送确认请求给用户
- MVP 阶段默认 `never`（不确认），生产环境建议设为 `dangerous`

**审计日志**:
- 所有工具调用（包括参数和返回值）写入 `~/.moguangclaw/logs/tool_audit.jsonl`
- 每条记录包含: 时间戳、session_id、tool_name、参数、返回值摘要、执行耗时

---

## 4. 打包与部署方案

### 4.1 运行环境说明

| 环境 | 架构 | 用途 |
|------|------|------|
| 开发机 | macOS, Apple M2 (arm64) | 本地开发调试 |
| 生产服务器 | Linux, x86_64 (amd64) | Docker 部署运行 |

> ⚠️ **跨架构注意**: M2 Mac 是 `arm64`，云服务器通常是 `amd64`。Docker 镜像必须指定目标平台构建，不能直接在 Mac 上 `docker build` 然后推到 x86 服务器运行。

### 4.2 Docker 镜像构建

使用 **多阶段构建 (Multi-stage Build)** + **多平台构建 (Multi-platform Build)**：

**Dockerfile**:
```dockerfile
# ---- 构建阶段 ----
FROM --platform=$TARGETPLATFORM python:3.13-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config.yaml .

# ---- 运行阶段 ----
FROM --platform=$TARGETPLATFORM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app .

# 确保 Python 能找到 src 下的 moguangclaw 包
ENV PYTHONPATH=/app/src

# Workspace 挂载点
VOLUME /root/.moguangclaw/workspace

# Gateway HTTP 端口（健康检查 + Webhook 备用入口）
EXPOSE 8080
CMD ["python", "-m", "moguangclaw.main"]
```

### 4.3 跨平台构建命令

在 M2 Mac 上构建 x86_64 Linux 镜像：

```bash
# 1. 启用 Docker Buildx（M2 Mac Docker Desktop 默认支持）
docker buildx create --name moguang-builder --use

# 2. 构建并推送多平台镜像到镜像仓库
docker buildx build \
  --platform linux/amd64 \
  -t your-registry/moguangclaw:latest \
  --push .

# 或者导出为本地 tar（不推送）
docker buildx build \
  --platform linux/amd64 \
  -t moguangclaw:latest \
  --output type=docker,dest=moguangclaw-amd64.tar .
```

### 4.4 生产部署（Docker Compose）

```yaml
# docker-compose.yml
version: "3.8"
services:
  moguangclaw:
    image: your-registry/moguangclaw:latest
    container_name: moguangclaw
    restart: always
    ports:
      - "8080:8080"   # Gateway HTTP（健康检查 /health + Webhook 备用）
    volumes:
      - ./workspace:/root/.moguangclaw/workspace   # 持久化 workspace
      - ./config.yaml:/app/config.yaml             # 配置文件
    environment:
      - QIANWEN_API_KEY=${QIANWEN_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DINGTALK_APP_KEY=${DINGTALK_APP_KEY}
      - DINGTALK_APP_SECRET=${DINGTALK_APP_SECRET}
```

### 4.5 部署流程

```
开发机 (M2 Mac)                         云服务器 (Linux x86_64)
┌──────────────┐                       ┌──────────────────────┐
│ 编写代码      │                       │                      │
│      │       │                       │  docker compose up   │
│      ▼       │     docker push       │         │            │
│ buildx build ├──────────────────────► │         ▼            │
│ --platform   │                       │  MoguangClaw 运行     │
│ linux/amd64  │                       │  (x86_64 容器)        │
└──────────────┘                       └──────────────────────┘
```

---

## 5. 技术栈

| 层级 | 技术选型 |
|------|---------|
| 语言 | Python 3.13 |
| 异步框架 | `asyncio` |
| LLM SDK | `dashscope` (Qianwen) + `openai` (OpenAI) |
| 钉钉接入 | `dingtalk-stream` |
| CLI 界面 | `rich` |
| 配置管理 | YAML (`pyyaml`) |
| 提示词模板 | `Jinja2` |
| 容器化 | Docker + Docker Compose |
| 跨平台构建 | Docker Buildx |

---

## 6. 项目目录结构

```
MoguangClaw/
├── docs/                          # 项目文档
│   └── architecture.md
├── src/
│   └── moguangclaw/
│       ├── __init__.py
│       ├── main.py                # 入口
│       ├── config.py              # 配置加载
│       ├── gateway/               # 网关服务
│       │   ├── server.py
│       │   ├── session.py
│       │   └── heartbeat.py
│       ├── channels/              # 消息渠道适配
│       │   ├── base.py
│       │   ├── cli.py
│       │   └── dingtalk.py
│       ├── agent/                 # Agent 核心
│       │   ├── runner.py
│       │   ├── loop.py            # Agentic Loop (ReAct)
│       │   └── context.py         # 上下文组装与裁剪
│       ├── llm/                   # LLM 接口层
│       │   ├── base.py
│       │   ├── qianwen.py
│       │   └── openai_provider.py
│       ├── tools/                 # 工具引擎
│       │   ├── base.py
│       │   ├── bash.py
│       │   ├── file_ops.py
│       │   └── registry.py
│       └── memory/                # 记忆系统
│           ├── context_builder.py # 上下文组装
│           ├── pruner.py          # Session Pruning
│           ├── compactor.py       # Compaction 压缩
│           └── store.py           # 持久化存储
├── tests/
├── workspace/                     # 工作区初始模板（首次启动时拷贝到 ~/.moguangclaw/workspace/）
│   ├── AGENTS.md
│   ├── SOUL.md
│   ├── MEMORY.md
│   └── skills/
├── Dockerfile
├── docker-compose.yml
├── config.yaml
└── requirements.txt
```

---

## 7. 开发阶段规划

### Phase 1：核心 Agent 能力（MVP）
- 搭建项目骨架
- 实现 LLM Provider（Qianwen + OpenAI）
- 实现基础工具（bash, read_file, write_file）
- 实现 Agentic Loop (ReAct 循环)
- 实现 CLI Channel
- 实现 **滑动窗口记忆**（最近 N 轮）

### Phase 2：钉钉接入 + 记忆增强
- 接入钉钉 Channel（dingtalk-stream）
- 实现 Gateway Server（会话路由、消息队列）
- 实现 Session Pruning（Soft Trim / Hard Clear）
- 实现心跳调度器

### Phase 3：生产化
- Compaction（摘要压缩）+ Memory Flush
- Docker 多平台构建 + 部署
- 模型 Failover
- 日志与监控
