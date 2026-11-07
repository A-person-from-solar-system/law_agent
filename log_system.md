# 法律 Agent 日志与调用监控系统规划

## 1. 建设目标

为当前法律 Agent 增加一套能够按用户、会话和单次请求追踪的日志系统，解决以下问题：

- 查看某个用户在什么时间发起了哪一轮 Agent 请求；
- 还原该轮请求经历的上下文组装、模型生成、工具调用和结果返回过程；
- 查看工具名称、调用参数、执行耗时、返回摘要、来源 ID 和失败原因；
- 区分问题发生在 Python 中台、Agent Engine、模型服务还是外部 RAG；
- 统计不同用户和服务的调用量、token 用量、成功率、延迟和错误分布；
- 在不泄露案件材料、账号信息和服务密钥的前提下，为线上排查和质量评估提供依据。

本系统不记录或展示模型隐藏推理过程。监控范围只包括系统实际可获得的请求元数据、上下文统计、工具调用、模型用量、最终状态和业务结果。

## 2. 当前项目已经具备的基础

当前系统不是完全没有日志能力，已经存在以下基础：

- FastAPI 中台会为请求生成或接收 `X-Request-ID`；
- `requestId` 会从中台传入 Agent Engine，并随 SSE 事件返回；
- Agent Engine 已记录运行完成和运行失败日志；
- Agent Engine 已统计请求数、成功数、失败数、取消数、上下文拦截数、活跃流数量和工具调用次数；
- SSE 已包含运行开始、文本增量、工具开始、工具完成、用量、运行完成和运行失败等事件；
- PostgreSQL 已保存会话消息、Agent 原始消息、工具调用 ID、用量和失败原因。

目前的主要不足是：日志分散在不同进程中，无法直接按用户查询；工具参数和执行轨迹没有形成独立审计记录；现有指标保存在进程内，重启后会丢失；也没有统一的管理查询、监控面板和告警。

## 3. 总体设计

日志系统分为三层：

### 3.1 结构化运行日志

Python 中台和 Node.js Agent Engine 都向标准输出写 JSON 日志，用于开发调试和故障排查。所有日志使用统一字段，并通过 `requestId` 关联。

这类日志主要保存运行信息，不默认保存完整用户问题、案件正文、模型回答和 RAG 原文。

### 3.2 Agent 审计轨迹

由 Python 中台把每轮 Agent Run、工具调用和关键事件保存到 PostgreSQL。中台掌握用户身份，因此用户与调用记录的关联只保存在中台，不需要把员工号、姓名等身份信息传给 Agent Engine。

审计轨迹用于回答“这个用户的这一轮请求具体发生了什么”，是管理后台查询和问题复盘的主要数据源。

### 3.3 指标与告警

将请求量、成功率、耗时、token 用量和错误类型转换成可聚合指标。试点阶段可以先在 PostgreSQL 上生成统计；需要长期运行时，再接入 Prometheus + Grafana，并使用 Loki、Elasticsearch 或其他集中式日志系统收集 JSON 日志。

### 3.4 两类前端界面

前端分成两类，避免把审计能力混入普通聊天界面：

- **现有业务前端 `frontend/`：** 继续负责聊天、SSE 展示和用户反馈，只显示本轮 `requestId`、公开工具状态和用户友好错误，不展示工具完整参数、RAG 原文和内部错误堆栈；
- **独立日志管理前端 `log-admin/`：** 使用当前管理员账号登录，通过 Python 中台的管理员接口查询运行记录、工具调用、指标和错误时间线。

两套前端都只访问 Python 中台。日志管理前端不能直接访问 Agent Engine、数据库或外部 RAG，也不能持有任何内部服务 token。

```text
浏览器
  │ JWT + X-Request-ID
  ▼
Python 中台 ────── PostgreSQL 审计表
  │ requestId           ├─ Agent Run
  │                     ├─ Tool Call
  │                     └─ Run Event
  ▼
Agent Engine ───── JSON 运行日志 / 指标
  │
  ├─ 模型服务
  └─ Python 知识接口 ── 外部 RAG

所有阶段通过 requestId 关联，工具调用通过 toolCallId 关联。
```

日志查询链路为：

```text
管理员
  ▼
日志管理前端 ── 管理员 JWT ──► Python 中台管理接口
                                      │ 权限校验 + 脱敏
                                      ▼
                              PostgreSQL 审计表
```

## 4. 追踪标识设计

### 4.1 `requestId`

继续使用当前已有的 `requestId` 作为一次请求的全链路追踪标识。它从浏览器或 Python 中台产生，并传递给 Agent Engine、知识检索接口和所有相关日志。

### 4.2 `runId`

中台为每轮 Agent 执行创建数据库主键 `runId`。`requestId` 用于跨服务查询，`runId` 用于数据库表之间的关联。

### 4.3 `turnId`

沿用当前会话中的 `turnId`，关联本轮用户消息、工具消息和最终回复。

### 4.4 `toolCallId`

沿用 Agent 框架生成的 `toolCallId`，把工具开始、工具完成和工具失败事件配对。

推荐的关联关系为：

```text
userId
  └─ sessionId
       └─ turnId
            └─ requestId / runId
                 └─ toolCallId
```

## 5. 需要记录的事件

不应把每一个 `text.delta` 都单独写入数据库，否则一次长回答可能产生大量写操作。数据库只保存关键状态事件，增量文本继续通过 SSE 发送，最终回答仍保存到现有消息表。

建议记录以下事件：

| 事件 | 记录内容 | 当前状态 |
| --- | --- | --- |
| `run.received` | 用户、会话、案件、请求来源 | 需新增 |
| `context.built` | 历史消息数、checkpoint 版本、案件材料长度 | 需新增 |
| `context.checked` | 估算输入 token、输出预留、安全余量、是否通过 | 需新增 |
| `model.started` | 模型供应商、模型名称、开始时间 | 需新增 |
| `model.first_token` | 首个文本增量时间、首字延迟 | 需新增 |
| `tool.started` | 工具名、调用参数摘要、`toolCallId` | 已有事件，需持久化和补充参数 |
| `tool.completed` | 是否成功、耗时、返回摘要、`sourceId` | 已有事件，需持久化和补充耗时 |
| `run.completed` | 总耗时、token 用量、工具调用次数 | 已有事件，需持久化 |
| `run.failed` | 错误码、发生阶段、是否可重试 | 已有事件，需持久化 |
| `run.cancelled` | 客户端断开或主动取消 | 当前有取消状态，需形成事件 |
| `checkpoint.queued` | 触发原因、会话轮次、估算 token | 需新增 |
| `checkpoint.completed` | 新版本、覆盖位置、摘要耗时 | 需新增 |
| `checkpoint.failed` | 摘要模型或格式校验错误 | 需新增 |

## 6. 数据库设计

### 6.1 `agent_runs`：每轮 Agent 请求

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | `runId`，UUID 主键 |
| `request_id` | 全链路追踪标识，唯一索引 |
| `turn_id` | 对应会话轮次 |
| `user_id` | 发起请求的用户 |
| `session_id` | 所属会话 |
| `case_id` | 本轮引用的案件，可为空 |
| `status` | `running/completed/failed/cancelled/rejected` |
| `model_provider` | 模型供应商 |
| `model_id` | 模型名称 |
| `checkpoint_version` | 本轮使用的摘要版本 |
| `history_message_count` | 注入的历史消息数量 |
| `estimated_input_tokens` | 调用前估算的输入 token |
| `input_tokens` | 模型实际返回的输入 token |
| `output_tokens` | 模型实际返回的输出 token |
| `tool_call_count` | 工具调用次数 |
| `started_at` | 开始时间 |
| `first_token_at` | 首次输出文本的时间 |
| `completed_at` | 结束时间 |
| `duration_ms` | 总耗时 |
| `error_stage` | `context/model/tool/agent/rag/stream/storage` |
| `error_code` | 标准错误码 |
| `error_message_safe` | 脱敏后的错误说明 |

必要索引：

- `request_id` 唯一索引；
- `(user_id, started_at)`；
- `(session_id, started_at)`；
- `(status, started_at)`；
- `(error_code, started_at)`。

### 6.2 `agent_tool_calls`：工具调用记录

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 数据库主键 |
| `run_id` | 关联 `agent_runs` |
| `tool_call_id` | Agent 工具调用标识 |
| `tool_name` | 当前为 `search_legal_kb` |
| `status` | `running/completed/failed/timeout` |
| `arguments_safe` | 脱敏后的参数或参数摘要 |
| `arguments_hash` | 原始参数哈希，用于判断两次调用是否相同 |
| `result_summary` | 候选数、保留数、截断数和估算 token |
| `source_ids` | 本次实际返回的来源 ID |
| `is_error` | 是否失败 |
| `error_code` | 工具或 RAG 错误码 |
| `started_at` | 开始时间 |
| `completed_at` | 完成时间 |
| `duration_ms` | 执行耗时 |

对当前 RAG 工具，`result_summary` 可以保存：

```json
{
  "totalCandidates": 20,
  "evidenceCount": 5,
  "omittedCount": 15,
  "estimatedTokens": 1130,
  "sourceTypes": ["case", "statute"]
}
```

普通日志只保存该摘要和 `sourceId`，不保存完整 `excerpt`。完整工具结果已经存在 Agent 原始消息中，如确需长期审计，可在受控存储中加密保存，而不是重复写入日志文件。

### 6.3 `agent_run_events`：关键事件时间线

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 自增主键 |
| `run_id` | 所属 Agent Run |
| `sequence_no` | 本轮内事件序号 |
| `event_type` | 事件类型 |
| `event_time` | 发生时间 |
| `service` | `mid-layer/agent-engine/rag/model` |
| `tool_call_id` | 工具事件时填写 |
| `payload_safe` | 脱敏后的结构化详情 |

为避免数据膨胀，只持久化关键事件，不保存 SSE 心跳和每个文本增量。对 `(run_id, sequence_no)` 建立唯一约束，防止重复写入。

## 7. 工具指令与返回结果的记录策略

用户希望查看工具调用指令和工具返回结果，但法律场景的数据敏感度较高，建议支持三种内容模式：

### 7.1 `metadata`：生产环境默认

- 工具参数只记录字段名、字符数、查询哈希、检索模式和数量限制；
- 工具结果记录命中数、`sourceId`、来源类型、相关性分数和截断情况；
- 不记录完整查询文本和证据正文。

### 7.2 `redacted`：受控排查

- 保存经过规则脱敏的查询预览；
- 对姓名、手机号、身份证号、地址、案号等敏感字段进行遮盖；
- 证据正文只保存短预览，设置严格长度上限。

### 7.3 `full_encrypted`：特殊审计

- 仅在确有审计需求时开启；
- 完整工具参数和结果单独加密保存；
- 普通管理员无权直接读取，只有审计角色经过授权后查看；
- 设置较短保留期限，并记录每一次查看行为。

建议环境变量：

```text
TRACE_ENABLED=true
TRACE_CONTENT_MODE=metadata
TRACE_RETENTION_DAYS=30
TRACE_TOOL_PREVIEW_CHARS=200
TRACE_FLUSH_INTERVAL_MS=1000
```

任何模式下都禁止记录：

- 模型 API Key、JWT、内部服务 token；
- HTTP `Authorization` 请求头；
- 数据库连接密码；
- 模型隐藏推理内容；
- 未经脱敏的身份证号、手机号等敏感信息。

## 8. 结构化日志字段规范

Python 和 Node.js 应统一以下字段名称：

```json
{
  "timestamp": "2026-09-11T10:20:30.123+08:00",
  "level": "info",
  "service": "agent-engine",
  "environment": "production",
  "event": "tool.completed",
  "requestId": "req-xxx",
  "runId": "run-xxx",
  "sessionId": "session-xxx",
  "toolCallId": "tool-xxx",
  "toolName": "search_legal_kb",
  "durationMs": 832,
  "status": "completed",
  "isError": false,
  "evidenceCount": 5,
  "errorCode": null
}
```

`userId` 只由 Python 中台记录。Agent Engine 使用 `requestId` 即可，排查时由中台将请求与用户关联，避免用户身份在多个服务中扩散。

## 9. 三个现有项目及日志管理前端的改造方案

### 9.1 改造职责总览

| 项目 | 在日志系统中的职责 | 改造程度 |
| --- | --- | --- |
| `frontend/` | 继续传递请求标识、显示可复制的请求编号、提供错误反馈入口 | 小幅修改 |
| `mid-layer/` | 关联用户、持久化轨迹、脱敏、权限校验、统计和管理 API | 核心改造 |
| `agent-engine/` | 采集模型、上下文和工具内部运行信息 | 必须补充 |
| `log-admin/` | 管理员查看日志、调用时间线、工具记录和统计 | 新增项目 |

如果第一版只需要事后查看最终工具消息，可以先从现有 `chat_messages.agent_message` 中提取，中台先行开发；但要准确得到工具调用参数、首字延迟、上下文预算、工具耗时和失败阶段，就必须同时修改 Agent Engine。

### 9.2 现有业务前端 `frontend/`

当前业务前端已经在聊天请求中生成 `X-Request-ID`，第一版不需要改变聊天协议，只需要增强请求追踪和用户反馈。

建议新增或修改：

```text
frontend/src/
├─ lib/api/chat.ts                       # 返回或暴露本轮 requestId
├─ lib/api/contracts.ts                  # 补充公开日志、反馈数据类型
├─ lib/api/feedback.ts                   # 新增错误回答反馈接口客户端
├─ hooks/use-chat-stream.ts              # 保存当前 requestId 和终态
├─ components/chat/streaming-message.tsx # 错误时展示可复制的请求编号
├─ components/chat/message-bubble.tsx    # 可选：增加“反馈回答问题”入口
└─ components/workspace/app-sidebar.tsx  # 可选：管理员日志系统跳转入口
```

具体改造：

1. `src/lib/api/chat.ts`
   - 保留现有浏览器端 `requestId` 生成逻辑；
   - 让调用方能够获得本轮 `requestId`，不能只在函数内部使用；
   - HTTP 错误和流中断时统一携带该标识。
2. `src/hooks/use-chat-stream.ts`
   - 在流状态中保存 `requestId`；
   - `run.completed`、`run.failed` 和客户端取消后保留该标识；
   - 防止下一轮请求覆盖上一轮尚未结束的追踪状态。
3. `src/components/chat/streaming-message.tsx`
   - 失败提示旁增加“复制请求编号”；
   - 用户报障时可以直接把编号交给管理员；
   - 不向普通用户显示内部错误堆栈和工具详细参数。
4. `src/components/chat/message-bubble.tsx`
   - 可选增加“回答有误”反馈按钮；
   - 提交 `requestId、messageId、问题分类和用户备注`，不重复上传完整案件材料。
5. `src/components/workspace/app-sidebar.tsx`
   - 如果日志系统部署在同一入口下，可以只为管理员显示“运行日志”链接；
   - 如果使用独立域名，则打开独立日志管理前端，并继续使用同一中台账号登录。

业务前端只消费公开 SSE 字段。即使 Agent Engine 的内部事件增加工具参数，Python 中台也必须在转发前删除内部审计字段。

### 9.3 Python 中台 `mid-layer/`

建议新增：

```text
mid-layer/app/observability/
├─ context.py          # requestId、runId 和用户上下文
├─ logging.py          # JSON 日志与敏感字段过滤
├─ trace_service.py    # Agent Run 与事件写入
├─ metrics.py          # 计数器和耗时指标
└─ redaction.py        # 查询参数和错误信息脱敏
```

同时建议新增：

```text
mid-layer/app/
├─ db/models/agent_trace.py            # Agent Run、工具调用和事件模型
├─ repositories/agent_trace_store.py   # 轨迹写入、批量事件写入和查询
├─ schemas/agent_trace.py              # 管理接口请求/响应结构
└─ api/routers/admin_agent_logs.py      # 管理员日志查询接口
```

需要调整的现有模块：

- `app/main.py`
  - 中间件绑定 `requestId`；
  - 增加结构化 HTTP 访问日志；
  - 注册管理员日志路由；
  - 对异常日志统一执行敏感字段过滤。
- `app/api/routers/chat.py`
  - 鉴权和会话校验通过后创建 `agent_runs`；
  - 关联 `userId、sessionId、turnId、caseId、requestId`；
  - 记录完成、失败、取消和客户端断开；
  - 在清理阶段保证 Run 最终进入可识别状态。
- `app/services/context_builder.py`
  - 记录历史消息数量、checkpoint 版本、是否绑定案件及各部分长度；
  - 不记录完整系统提示词、案件正文和历史消息；
  - 接收 Agent Engine 返回的预算明细后更新 Run。
- `app/services/agent_client.py`
  - 捕获 `run.started、tool.started、tool.completed、usage、run.completed、run.failed`；
  - 将工具和关键事件先缓冲，结束时批量保存；
  - 不把每个 `text.delta` 写入数据库；
  - 将内部 SSE 映射成公开 SSE，删除参数详情、内部错误和其他审计字段；
  - 校验事件 `requestId` 与当前请求一致。
- `app/api/routers/internal_rag.py`
  - 将 `requestId` 和 `toolCallId` 继续传入 RAG 客户端；
  - 记录知识接口入口、完成和错误事件；
  - 保持内部服务鉴权。
- `app/services/rag_client.py`
  - 记录外部 RAG 的连接和总耗时；
  - 保存检索模式、候选数、最终证据数和错误类型；
  - 普通日志只保留 `sourceId` 和结果摘要，不保存完整 `excerpt`。
- `app/services/compaction.py`
  - 记录摘要排队、开始、完成、失败和版本变化；
  - 将摘要日志与触发任务的会话关联。
- `app/api/dependencies.py`
  - 管理日志接口继续使用管理员 JWT 鉴权；
  - 后续如增加审计员，再新增 `auditor` 角色或独立权限依赖。
- `migrations/`
  - 使用 Alembic 创建 `agent_runs、agent_tool_calls、agent_run_events` 及索引。

中台是唯一负责把 `userId` 与 Agent Run 关联的服务。不要为了日志监控把员工号、姓名或角色传给 Agent Engine。

### 9.4 Agent Engine `agent-engine/`

需要调整：

- `src/routes/agent-runs.ts`
  - 在预算校验前后记录运行开始和 `context.checked`；
  - 从第一条 `text.delta` 计算首字延迟；
  - 记录模型、总耗时、实际 token、终态和错误阶段；
  - 客户端断开和运行超时时记录取消或失败原因；
  - 所有记录只使用 `requestId/sessionId`，不接收用户身份。
- `src/context/context-budget.ts`
  - 将各预算项形成结构化结果：系统提示词、工具定义、历史、当前问题、输出预留和安全余量；
  - 日志只记录数量，不记录原始文本。
- `src/agent/event-mapper.ts`
  - 为内部 `tool.started` 补充经过脱敏的参数摘要；
  - 为 `tool.completed` 补充耗时、错误码和结果摘要；
  - 如果框架开始事件不能直接提供完整参数，则在工具包装层记录，不能猜测或拼造参数。
- `src/tools/legal-kb-tool.ts`
  - 记录工具实际开始和结束时间；
  - 形成查询长度、检索模式、limit 等安全参数；
  - 记录调用次数限制、候选数、裁剪后证据数、`sourceId` 和估算 token；
  - 区分参数错误、调用次数超限、超时和执行失败。
- `src/tools/http-legal-kb-client.ts`
  - 向中台知识接口传递 `requestId/toolCallId`；
  - 记录 HTTP 状态和耗时，不记录内部 token 和完整响应体。
- `src/observability/logger.ts`
  - 统一 JSON 字段；
  - 扩展敏感字段过滤；
  - 确保不输出密钥、请求头、完整 prompt、案件正文和底层响应体。
- `src/observability/metrics.ts`
  - 增加首字延迟、Run 总耗时、模型错误、工具耗时、工具错误和上下文拒绝分类；
  - 当前内存指标保留用于健康检查，后续增加 Prometheus 导出。
- `src/config/env.ts`
  - 增加日志开关、内容模式、预览长度和指标开关；
  - 生产环境默认使用 `metadata`，禁止默认保存全文。

Agent Engine 到 Python 中台的 SSE 属于内部协议，可以携带必要的审计摘要；Python 中台到业务前端的是公开协议，必须显式选择允许返回的字段，不能直接原样转发新增的内部字段。

### 9.5 独立日志管理前端 `log-admin/`

建议单独创建日志管理前端，继续使用 Next.js 和当前中台账号体系，避免重新维护一套用户表和密码。

建议目录：

```text
log-admin/src/
├─ app/login/page.tsx
├─ app/runs/page.tsx
├─ app/runs/[runId]/page.tsx
├─ app/metrics/page.tsx
├─ components/run-filter.tsx
├─ components/run-table.tsx
├─ components/run-timeline.tsx
├─ components/tool-call-panel.tsx
├─ components/error-panel.tsx
├─ lib/api/client.ts
├─ lib/api/agent-runs.ts
├─ lib/api/metrics.ts
└─ lib/auth/token-store.ts
```

登录与权限流程：

1. 登录页调用当前中台 `/api/auth/login`；
2. 使用返回的管理员 JWT 调用日志管理接口；
3. 页面加载时调用 `/api/auth/me`；
4. 非管理员立即拒绝进入日志页面；
5. 中台仍需再次校验角色，前端判断只用于界面控制，不能作为安全边界。

第一版页面功能：

- 按时间、用户、会话、请求 ID、状态和错误码筛选；
- 查看单轮 Agent Run 时间线；
- 展示模型、token、总耗时和首字延迟；
- 查看工具参数摘要、命中来源和失败原因；
- 从日志跳转到对应会话和消息；
- 对受保护内容执行二次确认和审计授权。

普通用户只能查看自己的会话状态；完整运行轨迹仅管理员或审计角色可访问。

部署建议：

- 优先由同一 Nginx 入口挂载，例如业务系统 `/`、日志系统 `/logs`、中台 `/backend`；
- 如果日志系统使用独立域名，中台只允许该日志域名跨域访问；
- 两个前端可以共用中台账号，但不建议跨域共享浏览器本地 token，独立日志前端重新登录更清晰；
- 日志前端不得接收或保存 Agent Engine、RAG 的内部服务 token。

## 10. 管理查询接口规划

建议新增管理员接口：

```text
GET /api/admin/agent-runs
GET /api/admin/agent-runs/{run_id}
GET /api/admin/agent-runs/{run_id}/events
GET /api/admin/agent-runs/{run_id}/tool-calls
GET /api/admin/agent-metrics/summary
GET /api/admin/agent-metrics/errors
```

列表接口支持：

- 时间范围；
- 用户或员工号；
- 会话和案件；
- 模型名称；
- 成功、失败、取消和上下文拒绝；
- 工具是否调用；
- 错误码；
- 耗时和 token 区间。

接口必须复用当前管理员鉴权，所有日志详情查询还要单独记录审计日志，防止管理员无痕查看敏感案件内容。

## 11. 指标和监控面板

### 11.1 运行指标

- 每分钟 Agent Run 数；
- 当前活跃 Run 数；
- 成功率、失败率和取消率；
- 平均、P50、P95、P99 总耗时；
- 首字延迟；
- 上下文预算拒绝次数；
- 不同错误码出现次数。

### 11.2 模型指标

- 按模型统计请求数和成功率；
- 输入、输出和总 token；
- 模型超时与不可用次数；
- 单用户和全系统 token 使用趋势。

### 11.3 工具与 RAG 指标

- 工具调用次数和平均每轮调用数；
- 工具成功率、超时率和平均耗时；
- RAG 候选数、最终证据数和截断数；
- 空结果率；
- `RAG_TIMEOUT`、`RAG_UNAVAILABLE`、`RAG_INVALID_RESPONSE` 分布。

### 11.4 推荐告警

- 5 分钟内 Agent Run 失败率超过设定阈值；
- P95 响应时间持续升高；
- 模型或 RAG 超时连续出现；
- 活跃 Run 数接近并发上限；
- 上下文拒绝次数突然增加；
- 单个用户短时间内调用量或 token 用量异常；
- 审计日志写入持续失败。

具体阈值应根据内部试点数据确定，不建议在没有基线时直接写死。

## 12. 性能与可靠性要求

- 日志写入不能阻塞模型文本流；
- 不对每个 `text.delta` 执行数据库写入；
- 工具和关键事件先在内存中缓冲，在完成、失败或定时触发时批量写入；
- Agent Run 主记录必须在请求开始时创建，结束时更新终态；
- 审计写入失败不能直接导致本轮法律问答失败，但必须产生本地告警日志；
- 对 `(request_id)` 和 `(run_id, sequence_no)` 设置唯一约束，保证重复提交时幂等；
- 日志系统不可用时，SSE 主链路仍能运行，并在恢复后尽可能补写终态；
- 定期删除超过保留期的详细事件，只保留必要的聚合统计。

## 13. 分阶段落地计划

### 第一阶段：可追踪的最小版本

目标：能通过 `requestId` 查询某个用户的一轮 Agent 调用。

- 业务前端保留并展示可复制的 `requestId`；
- 统一 Python 与 Node.js JSON 日志字段；
- 新增 `agent_runs` 和 `agent_tool_calls` 表；
- 在中台记录用户、会话、模型、终态、耗时、token 和错误码；
- Agent Engine 补充工具参数摘要、执行耗时和上下文预算信息；
- 持久化工具名称、参数摘要、结果摘要和 `sourceId`；
- 默认启用 `metadata` 内容模式；
- 增加管理员列表与详情接口；
- 创建 `log-admin/`，先完成管理员登录、运行列表和基础详情页。

### 第二阶段：运行时间线与问题定位

目标：能够还原一次请求停在哪个阶段。

- 新增 `agent_run_events`；
- 记录上下文检查、首字输出、工具执行、运行结束和摘要任务；
- 在日志管理前端增加单次 Run 时间线和工具详情页面；
- 增加错误码、耗时和用户维度筛选；
- 在业务前端增加“回答有误”反馈入口；
- 补充日志脱敏和权限测试。

### 第三阶段：监控与告警

目标：从被动查日志变为主动发现异常。

- 接入 Prometheus + Grafana；
- 将 JSON 日志汇总到 Loki 或现有日志平台；
- 建立成功率、P95 延迟、模型用量、工具成功率和错误分布面板；
- 配置模型超时、RAG 异常和错误率告警。

### 第四阶段：质量闭环

目标：让线上日志反向支持 Agent 评估和优化。

- 对用户反馈的问题按 `requestId` 标注原因；
- 将问题归类为上下文、检索、工具、模型生成或前端展示；
- 对脱敏后的失败样例建立回归评测集；
- 每次调整模型、提示词、RAG 或压缩策略后执行回归；
- 对比修改前后的准确性、工具调用质量、延迟和 token 成本。

## 14. 测试与验收标准

### 14.1 功能验收

- 每轮请求都能通过 `requestId` 找到唯一 Agent Run；
- Agent Run 能关联正确的用户、会话、轮次和案件；
- 每个 `tool.started` 都能与对应的 `tool.completed` 或失败状态配对；
- 成功、模型失败、工具超时、上下文超限和客户端断开都有明确终态；
- 管理员可以按用户、错误码和时间查询；
- 非管理员无法访问其他用户的运行轨迹。

### 14.2 安全验收

- 日志中不出现 API Key、JWT、内部 token 和数据库密码；
- `metadata` 模式下不出现完整用户问题、案件正文和证据原文；
- 脱敏规则覆盖手机号、身份证号、邮箱、地址等字段；
- 查看受保护内容的行为本身能够被审计；
- 到期日志可以按保留策略删除。

### 14.3 性能验收

- 日志开启前后对比首字延迟和总耗时；
- 长回答不会因逐 token 入库产生大量数据库写入；
- 日志存储暂时不可用时，Agent 主链路仍能返回；
- 高并发下不会出现不同用户的 `requestId`、工具调用或事件串联错误。

## 15. 推荐的第一版技术选型

考虑当前项目仍处于内部试点阶段，第一版不建议立即引入过多基础设施：

- **结构化日志：** Python 标准 logging 增加 JSON Formatter；Node.js 继续使用 Fastify/Pino；
- **审计数据：** 继续使用现有 PostgreSQL，通过 SQLAlchemy + Alembic 建表；
- **后台查询：** 增加 FastAPI 管理接口，复用现有管理员权限；
- **运行指标：** 第一版从审计表聚合，后续再接 Prometheus；
- **监控展示：** 使用独立 `log-admin/` 展示单次调用轨迹，规模扩大后再用 Grafana 展示聚合指标；
- **集中日志：** 部署阶段按现有环境选择 Loki 或 Elasticsearch，不作为第一版前置条件。

这套方案可以先解决“按用户还原一次 Agent 调用”的核心问题，同时为后续分布式追踪、评测闭环和生产告警保留扩展空间。

## 16. 实施优先级结论

最优先完成的不是可视化大屏，而是以下四项：

1. 统一 `requestId` 并建立 `agent_runs` 主记录；
2. 持久化工具调用参数摘要、返回摘要、`sourceId` 和耗时；
3. 建立内容脱敏、访问权限和日志保留策略；
4. 提供按用户、会话、请求 ID 和错误码查询的管理员接口。

完成这四项后，系统就可以回答：谁在什么时候发起了请求、Agent 调用了什么工具、工具返回了哪些来源、模型最终是否成功，以及异常发生在哪一个服务阶段。之后再逐步增加监控面板、告警和评测闭环。
