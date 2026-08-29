# 法律 Agent 第一阶段开发需求

## 1. 文档目的

本文定义法律 Agent 项目第一阶段的开发范围、功能需求、接口契约、质量要求和验收标准。

第一阶段只建设基于 `@earendil-works/pi-agent-core` 的 Node.js/TypeScript 无状态 Agent 计算引擎，用于验证以下核心链路：

```text
结构化请求
  → 请求级 Agent 创建
  → 法律知识库 Tool Calling
  → Tool 结果预算控制
  → LLM 流式推理
  → 标准 SSE 事件输出
  → 请求结束并释放 Agent
```

本阶段属于对 pi SDK 的业务封装与集成开发，不修改、Fork 或硬编码修改 pi 的上游开源源码。

## 2. 阶段目标

完成一个可以独立启动、独立测试的 `agent-engine` 服务。该服务应满足：

1. 使用 `@earendil-works/pi-agent-core` 创建请求级 `Agent`；
2. Agent 默认不具备文件读取、文件写入、代码编辑或命令执行能力；
3. 只允许调用显式注册的法律业务工具；
4. 支持装载模拟的历史消息、Checkpoint 和当前案件信息；
5. 支持法律知识库检索 Tool，并对 Tool 结果进行结构化瘦身和 Token 预算控制；
6. 将 Agent 生命周期、文本增量、Tool 调用、Usage 和错误转换为稳定的 SSE 协议；
7. 支持客户端断开、超时和主动取消；
8. 请求之间不共享用户会话状态；
9. 不依赖 Python、PostgreSQL、真实前端或正式知识库即可完成自动化测试；
10. 为第二阶段 Python/PostgreSQL 接入提供稳定的内部服务契约。

## 3. 技术边界

### 3.1 本阶段必须使用

- Node.js 支持的稳定运行版本，具体版本写入项目说明并在 CI 中固定；
- TypeScript 严格模式；
- `@earendil-works/pi-agent-core`；
- 与所选 pi-agent-core 版本兼容的 `@earendil-works/pi-ai`；
- Fastify 或同等级 Node.js HTTP 框架；
- JSON Schema 或 TypeBox 进行入参和 Tool 参数校验；
- Vitest 或同等级测试框架；
- npm lockfile 固定依赖版本。

pi 相关依赖必须锁定精确版本，不使用不受控的 `latest` 自动升级。升级依赖时应单独执行兼容性验证。

### 3.2 本阶段不包含

- Python FastAPI 网关；
- PostgreSQL 表、ORM、迁移和 Repository；
- JWT 登录、租户鉴权和正式权限系统；
- 正式外部法律知识库接入；
- Checkpoint 自动生成及持久化；
- 完整上下文压缩任务；
- 前端聊天页面；
- 文件上传和文档解析；
- 多 Agent 协作；
- 会话分支、树状会话、撤回和恢复；
- `pi-coding-agent` 的 CLI、TUI、Skills、Extensions 和 SessionManager；
- 生产部署、灰度发布和大规模压力测试。

上述能力如需测试，统一通过 Mock、Fixture 或接口占位实现，不得在第一阶段扩张为完整业务功能。

## 4. 总体架构

```text
测试客户端 / Postman / curl
          │
          │ POST /internal/v1/agent/runs
          ▼
Node.js Agent Engine
  ├─ 请求校验
  ├─ Context Assembler
  ├─ Context Budget Guard
  ├─ Legal Agent Factory
  ├─ SSE Event Mapper
  └─ Tool Registry（白名单）
          │
          ├─► LLM Stream Provider / Mock Stream Provider
          │
          └─► LegalKnowledgeClient
                 ├─ MockLegalKnowledgeClient（第一阶段默认）
                 └─ HttpLegalKnowledgeClient（只定义接口，可选联调）
```

Agent Engine 不保存长期会话。请求结束后，本轮上下文和 Agent 实例不作为下一请求的隐式状态继续使用。

## 5. 推荐目录结构

```text
lawAgent2.0/
  agent-engine/
    package.json
    package-lock.json
    tsconfig.json
    .env.example
    README.md
    src/
      server.ts
      app.ts
      config/
        env.ts
      routes/
        health.ts
        agent-runs.ts
      agent/
        create-legal-agent.ts
        system-prompt.ts
        event-mapper.ts
        message-validator.ts
      context/
        context-assembler.ts
        context-budget.ts
        checkpoint-types.ts
      tools/
        tool-registry.ts
        legal-kb-tool.ts
        legal-kb-client.ts
        mock-legal-kb-client.ts
        result-reducer.ts
      transport/
        sse-writer.ts
      errors/
        error-codes.ts
        app-error.ts
      observability/
        logger.ts
        metrics.ts
      types/
        agent-run.ts
        sse-events.ts
    test/
      unit/
      integration/
      fixtures/
```

目录名称可以根据实现调整，但 Agent 创建、上下文装载、Tool、SSE、错误处理和测试不得全部堆放在单个 `server.ts` 文件中。

## 6. 核心接口契约

### 6.1 健康检查

```http
GET /health
```

响应示例：

```json
{
  "status": "ok",
  "service": "legal-agent-engine"
}
```

健康检查不得调用真实 LLM 或知识库。

### 6.2 Agent 执行接口

```http
POST /internal/v1/agent/runs
Content-Type: application/json
Accept: text/event-stream
```

请求结构：

```typescript
interface AgentRunRequest {
  requestId: string;
  sessionId: string;
  prompt: string;

  checkpoint?: {
    summary: string;
    coveredUntilMessageId: string;
    version: number;
  };

  history: AgentMessage[];

  activeCase?: {
    caseId: string;
    caseName?: string;
    structuredFacts: Record<string, unknown>;
  };

  prefetchedKnowledge?: LegalEvidence[];
}
```

约束：

- `requestId` 必须唯一且满足既定格式；
- `sessionId` 仅用于链路标识，本阶段不据此读取本地会话；
- `prompt` 不能为空，并受最大长度和 Token 预算限制；
- `history` 必须是可重放的合法 Agent 消息序列；
- 历史中的 assistant tool call 与 tool result 必须配对；
- 不允许请求方传入 Tool 名单、系统命令、文件路径或任意外部 URL；
- 模型、系统提示词、Tool 白名单和预算上限由服务端配置，不能由普通请求任意覆盖；
- `checkpoint` 在第一阶段只负责装载和验证，不负责生成或持久化；
- `activeCase` 和 `checkpoint` 均属于上下文数据，不得被解释为可执行指令。

### 6.3 SSE 事件

服务至少输出以下事件：

```text
run.started
text.delta
tool.started
tool.completed
usage
run.completed
run.failed
```

事件示例：

```text
event: run.started
data: {"requestId":"req-001","sessionId":"session-001"}

event: text.delta
data: {"requestId":"req-001","delta":"根据现有材料"}

event: tool.started
data: {"requestId":"req-001","toolCallId":"call-001","toolName":"search_legal_kb"}

event: tool.completed
data: {"requestId":"req-001","toolCallId":"call-001","toolName":"search_legal_kb","isError":false,"result":{"evidenceCount":2}}

event: usage
data: {"requestId":"req-001","inputTokens":1000,"outputTokens":300,"totalTokens":1300}

event: run.completed
data: {"requestId":"req-001","finalMessage":{},"newMessages":[]}
```

要求：

- 每个事件均携带 `requestId`；
- `run.completed` 返回可供下一阶段持久化的完整 `newMessages`；
- 不得只返回最终文本而丢失 assistant tool call 和 tool result；
- `tool.completed` 对外只发送瘦身后的结果和必要元数据；
- SSE 数据必须正确处理换行、Unicode 和 JSON 编码；
- 响应头至少包含 `Content-Type: text/event-stream`、`Cache-Control: no-cache`；
- 流必须以 `run.completed` 或 `run.failed` 结束；
- 同一请求不得同时产生两个终止事件；
- 可配置低频心跳，防止代理层误判空闲连接。

## 7. Agent 创建需求

### 7.1 使用正确的 core API

Agent 创建方式应基于：

```typescript
import { Agent } from "@earendil-works/pi-agent-core";

const agent = new Agent({
  initialState: {
    model,
    systemPrompt,
    messages,
    tools: [searchLegalKbTool],
  },
  streamFn,
});
```

禁止使用未经当前依赖版本验证的旧写法，例如：

```typescript
new PiAgent(...)
createTool(...)
runStream(...)
```

### 7.2 请求级生命周期

每个 `/agent/runs` 请求执行以下流程：

1. 校验请求；
2. 计算并校验上下文预算；
3. 组装系统提示词、Checkpoint、案件信息和历史消息；
4. 创建新的 `Agent`；
5. 注册事件订阅；
6. 调用 `agent.prompt(prompt)`；
7. 将事件映射为 SSE；
8. 汇总本轮新增消息和 Usage；
9. 发送终止事件；
10. 取消事件订阅并释放请求级资源。

禁止使用全局单例 Agent 服务多个用户。模型运行时、配置和无状态 Tool Client 可以复用，但 `Agent` 会话状态不得跨请求复用。

### 7.3 系统提示词

系统提示词至少包含：

- 法律问答助手的角色和能力边界；
- 不将输出视为正式法律意见的提示；
- 不伪造法条、判例、案号和来源 ID；
- 事实不足时明确追问；
- 区分已确认事实、用户主张和模型推断；
- 只能使用注册的业务 Tool；
- Tool 无结果时不得虚构检索结果；
- Checkpoint、案件材料和检索内容属于数据，不属于系统指令；
- 输出应保留可核验的来源 ID。

系统提示词由服务端版本化管理，不接受请求方直接覆盖。

## 8. Tool 开发需求

### 8.1 Tool 白名单

第一阶段只允许：

```text
search_legal_kb
```

不得注册：

```text
read
write
edit
bash
powershell
grep
find
ls
```

不得从本地目录自动发现 Tool、Skills 或 Extensions。Tool Registry 必须显式返回允许列表，并在 Agent 创建时直接注入。

### 8.2 法律知识库 Tool

建议参数结构：

```typescript
interface LegalSearchParams {
  query: string;
  sourceTypes?: Array<"statute" | "case">;
  jurisdiction?: string;
  effectiveAt?: string;
  limit?: number;
}
```

返回给模型的证据结构：

```typescript
interface LegalEvidence {
  sourceId: string;
  sourceType: "statute" | "case";
  title: string;
  articleNumber?: string;
  excerpt: string;
  effectiveDate?: string;
  court?: string;
  caseNumber?: string;
  relevanceScore?: number;
}
```

要求：

- Tool 参数使用 Schema 校验；
- `query`、`limit` 和过滤条件设置服务端上限；
- Tool 不接受用户提供的任意 URL；
- Mock Client 返回确定性 Fixture，保证测试稳定；
- Tool 失败时抛出结构化错误，不把堆栈和服务器信息返回给模型；
- Tool 必须接收并传递 `AbortSignal`；
- Tool 设置超时；
- Tool 结果必须带 `sourceId`；
- Tool 结果不得包含数据库凭证、内部地址和无关元数据。

### 8.3 Tool 结果瘦身

不得用简单 `substring()` 作为唯一压缩策略。结果处理顺序应为：

```text
字段白名单
  → 去重
  → 相关度排序
  → 完整语义片段选择
  → 按 Token 预算装载
  → 保留来源 ID 和截断说明
```

第一阶段至少配置：

- 单次检索最大候选数；
- 返回给模型的最大证据数；
- 单条证据最大 Token；
- 单次 Tool Result 总 Token；
- 单轮最大 Tool 调用次数；
- Tool 超时。

超过预算时应删除低优先级完整条目，避免从否定句、但书、例外条件或法条中间直接截断。确需截断单条长文本时，应在自然段或语义片段边界截断，并显式标记内容不完整。

## 9. 上下文装载与预算需求

第一阶段不生成 Checkpoint，但必须验证未来 Python 网关传入的上下文能否安全装载。

### 9.1 Context Assembler

按以下来源组装本轮上下文：

```text
服务端系统提示词
+ Checkpoint（可选）
+ 当前案件结构化信息（可选）
+ 前置知识（可选）
+ Checkpoint 之后的完整历史 Turn
+ 当前用户 Prompt
```

不得把 Checkpoint 和案件数据直接拼接成无边界文本。必须使用固定标签或结构化序列化，并明确其数据属性。

### 9.2 Context Budget Guard

预算校验至少考虑：

- 系统提示词；
- Tool Schema；
- Checkpoint；
- 当前案件；
- 前置知识；
- 历史消息；
- 当前 Prompt；
- 预留模型输出；
- 安全余量。

本阶段不负责自动摘要，但在超预算时必须：

1. 返回明确的 `CONTEXT_BUDGET_EXCEEDED` 错误；或
2. 仅采用经过测试的完整 Turn 裁剪策略。

不得从 assistant tool call 与对应 tool result 中间切断历史，不得静默截断后继续执行且不记录告警。

## 10. 取消、超时和异常处理

### 10.1 客户端断开

当调用方关闭 SSE 连接时：

1. 触发请求级 `AbortController`；
2. 调用 `agent.abort()`；
3. 取消正在进行的 Tool HTTP 请求；
4. 停止继续写入 SSE；
5. 清理订阅和计时器；
6. 记录取消原因，但不记录完整案件文本。

### 10.2 超时

至少区分：

- 整轮 Agent 超时；
- 单次模型调用超时；
- 单次 Tool 调用超时；
- SSE 写入失败。

超时应使用统一错误码，且不能把底层密钥、URL、堆栈或供应商原始敏感响应发送给请求方。

### 10.3 错误码

第一阶段至少定义：

```text
INVALID_REQUEST
INVALID_MESSAGE_HISTORY
CONTEXT_BUDGET_EXCEEDED
MODEL_UNAVAILABLE
MODEL_TIMEOUT
TOOL_ARGUMENT_INVALID
TOOL_TIMEOUT
TOOL_EXECUTION_FAILED
RUN_CANCELLED
INTERNAL_ERROR
```

## 11. 配置需求

环境变量至少覆盖：

- 服务监听地址和端口；
- 日志级别；
- 模型 Provider 和模型 ID；
- 模型凭证；
- 模型调用超时；
- Agent 整轮超时；
- 最大输入 Token；
- 预留输出 Token；
- Tool 结果 Token 预算；
- Tool 最大调用次数；
- Mock 模式开关。

要求：

- 提供 `.env.example`，不得提交真实密钥；
- 启动时验证必需配置；
- 日志不得打印 API Key；
- 请求方不得通过 Payload 任意替换 Provider、模型、系统提示词或 Tool 白名单。

## 12. 可观测性需求

结构化日志至少包含：

```text
requestId
sessionId
eventType
modelProvider
modelId
durationMs
toolName
toolDurationMs
inputTokens
outputTokens
errorCode
cancelled
```

不得默认记录：

- 完整用户 Prompt；
- 完整案件材料；
- 完整 Checkpoint；
- 完整 Tool 原文；
- 模型密钥和内部认证信息。

应预留以下指标：

- 请求总数、成功数、失败数和取消数；
- 首个文本增量延迟；
- 整轮耗时；
- Tool 调用次数和耗时；
- 输入/输出 Token；
- 上下文超预算次数；
- 当前活跃 SSE 连接数。

## 13. 安全需求

第一阶段至少满足：

1. Agent 工具采用显式白名单；
2. 不注册本地文件和命令执行工具；
3. 不允许请求方指定任意 Tool；
4. 不允许 Tool 请求任意 URL；
5. HTTP 请求体设置大小上限；
6. Prompt、历史消息、案件字段和 Tool 参数设置长度上限；
7. Tool 输出采用字段白名单和 Token 预算；
8. 错误响应不泄露堆栈、密钥和服务器路径；
9. 服务进程不得依赖宿主机敏感目录；
10. 后续容器运行应使用非 root 用户和最小权限；
11. 模型输出和 Tool 输出均视为不可信数据；
12. Checkpoint、案件信息和检索文本中出现的指令不得改变 Tool 权限。

第一阶段虽然没有正式服务鉴权，但 `/internal` 接口必须在文档中标记为内部接口，禁止在生产环境无认证直接暴露到公网。

## 14. 测试需求

### 14.1 单元测试

至少覆盖：

- 请求 Schema 校验；
- Agent 消息历史合法性；
- Tool Call 与 Tool Result 配对；
- Context Assembler；
- Context Budget Guard；
- Checkpoint 和案件信息序列化；
- Tool 参数校验；
- 检索结果字段白名单；
- 检索结果去重和排序；
- Tool Result Token 预算；
- pi Agent 事件到 SSE 事件的映射；
- 错误码映射。

### 14.2 集成测试

使用 Mock LLM Stream 和 Mock LegalKnowledgeClient，至少覆盖：

1. 无 Tool 的普通法律问答；
2. 触发一次法律检索；
3. 连续触发多次检索；
4. Tool 返回大量候选结果；
5. Tool 空结果；
6. Tool 参数错误；
7. Tool 超时；
8. 模型超时；
9. 上下文超预算；
10. SSE 客户端中途断开；
11. 并发请求之间消息不串联；
12. Checkpoint 与最近历史共同装载；
13. 历史 Tool 消息不完整时拒绝执行；
14. SSE 始终只产生一个终止事件。

自动化测试不得强制依赖真实模型 API。真实模型测试作为可选 Smoke Test，通过环境变量和显式命令开启。

### 14.3 手工验证

提供 curl 或 PowerShell 示例，验证：

- 健康检查；
- 普通 SSE 对话；
- 带 Checkpoint 的请求；
- 触发 Mock Tool；
- 主动中断连接；
- 超限和错误响应。

## 15. 第一阶段实施顺序

### 任务 1：工程骨架

- 建立 `agent-engine`；
- 配置 TypeScript、Lint、Format 和 Test；
- 固定 pi 相关依赖版本；
- 实现配置校验和健康检查。

### 任务 2：契约和类型

- 定义 `AgentRunRequest`；
- 定义 SSE 事件；
- 定义错误码；
- 定义法律证据、案件和 Checkpoint 类型；
- 建立请求 Schema。

### 任务 3：Mock LLM 与基础 Agent

- 建立可注入 `streamFn`；
- 实现请求级 Agent Factory；
- 实现普通文本增量映射；
- 完成无 Tool 的端到端 SSE 测试。

### 任务 4：法律知识库 Tool

- 定义 `LegalKnowledgeClient`；
- 实现 Mock Client；
- 实现 `search_legal_kb`；
- 实现参数校验、超时和取消；
- 验证 Agent 能触发 Tool Calling。

### 任务 5：Tool 结果治理

- 字段白名单；
- 去重和排序；
- 完整证据片段选择；
- Token 预算；
- Tool Usage 和审计元数据。

### 任务 6：上下文装载与保护

- 装载 Checkpoint；
- 装载当前案件；
- 校验历史消息；
- 实现预算 Guard；
- 拒绝不完整 Tool 历史和超限请求。

### 任务 7：取消、错误和可观测性

- 传播 AbortSignal；
- 实现整轮及 Tool 超时；
- 标准化错误；
- 完成结构化日志和基础指标。

### 任务 8：测试与文档

- 完成单元测试和集成测试；
- 提供启动、配置和调用说明；
- 提供 curl/PowerShell 示例；
- 记录与第二阶段 Python 网关的对接契约。

## 16. 验收标准

第一阶段完成必须同时满足：

1. `agent-engine` 可以通过单一命令启动；
2. `/health` 返回正常；
3. `/internal/v1/agent/runs` 能输出合法 SSE；
4. 普通问答和 Tool Calling 均可运行；
5. Agent 只拥有 `search_legal_kb`，不存在文件和终端工具；
6. 请求之间不共享历史消息；
7. Tool 大结果能够按预算缩减且保留来源 ID；
8. Tool Call、Tool Result 和最终 Assistant Message 均能完整输出；
9. Checkpoint、当前案件和历史消息可以通过模拟 Payload 装载；
10. 超预算历史不会被无提示地发送给模型；
11. 客户端断开后 Agent 和 Tool 能及时取消；
12. 模型失败、Tool 失败和超时均返回标准错误事件；
13. 日志不泄露密钥、完整案件材料和服务器路径；
14. 自动化测试不依赖真实模型和正式知识库；
15. 核心单元测试和集成测试全部通过；
16. README 能指导第二名开发者独立启动并完成 Mock 调用。

## 17. 阶段交付物

第一阶段最终交付：

- `agent-engine` TypeScript 源码；
- 锁定版本的依赖清单；
- `.env.example`；
- 内部 Agent 执行接口说明；
- SSE 事件说明；
- Mock LLM/Mock Tool Fixture；
- 单元测试和集成测试；
- curl/PowerShell 调用示例；
- 错误码清单；
- 第一阶段测试报告；
- 第二阶段 Python/PostgreSQL 对接注意事项。

## 18. 第二阶段接口预留

第一阶段不实现 Python 和数据库，但输出必须能够支持第二阶段完成：

```text
Python 从 PostgreSQL 读取 Checkpoint 和消息
  → 调用 /internal/v1/agent/runs
  → 透传 SSE
  → 收集 newMessages、Tool 结果和 Usage
  → 在事务中写回 PostgreSQL
```

因此第一阶段不得把会话状态藏在 Node.js 全局内存、临时文件或 pi 本地 Session 中，也不得只返回无法恢复 Tool Calling 历史的最终文本。
