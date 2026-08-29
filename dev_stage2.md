# 法律 Agent Python 层开发文档（Dev Stage 2）

## 1. 文档定位

本文是 `dev1.0.md` 的 Python 层专项实施文档，目标是把 Python 服务建设为系统的**业务中台、数据中台和安全网关**。

Python 层负责所有与用户、权限、会话、案件、数据库、知识库和后台任务有关的有状态逻辑；Node.js `pi-agent-core` 只负责单次请求内的 Agent 推理、Tool 调度和流式生成。两者之间通过明确的 HTTP/SSE 契约解耦。

本文覆盖：

- FastAPI 工程结构；
- PostgreSQL 数据模型与持久化策略；
- 用户、会话和案件接口；
- 上下文切片与 Agent Payload；
- 内部 RAG 查询接口；
- Node.js SSE 代理及落盘；
- Checkpoint 异步压缩；
- 安全、异常、测试和阶段验收。

## 2. Python 层职责与边界

### 2.1 Python 负责

1. 用户注册、登录、JWT 校验和权限控制；
2. 用户、会话、消息和案件的持久化；
3. 通过 `user_id` 强制执行多租户隔离；
4. 根据 Checkpoint 和最近消息组装上下文；
5. 校验并加载当前显式绑定案件；
6. 对接外部法律知识库，提供只读内部接口；
7. 调用 Node.js `/agent/run` 并向前端转发 SSE；
8. 汇总 User、Tool、Assistant 和 Usage 后原子落盘；
9. 触发并执行后台 Checkpoint 摘要任务；
10. 统一处理限流、超时、日志、审计和错误响应。

### 2.2 Python 不负责

- 不维护每个用户的常驻 Agent 实例；
- 不在内存中保存跨请求会话状态；
- 不实现 `pi-agent-core` 的推理循环；
- 不负责外部法律知识的采集、清洗、Embedding 和索引构建；
- 不接受模型直接写入知识库或业务数据库；
- 不根据模糊语义猜测当前案件，案件作用域必须显式指定。

## 3. 技术选型

MVP 建议使用以下技术栈：

| 领域 | 建议技术 | 说明 |
| --- | --- | --- |
| Web 框架 | FastAPI | 原生异步、类型约束清晰、适合 SSE 代理 |
| 数据校验 | Pydantic v2 | 请求、响应、配置和服务间契约 |
| ORM | SQLAlchemy 2.x Async | 异步数据库访问和明确事务边界 |
| 数据库驱动 | asyncpg | PostgreSQL 异步驱动 |
| 数据库迁移 | Alembic | 禁止手工维护生产表结构 |
| HTTP 客户端 | httpx.AsyncClient | 调用 Node.js 和外部知识服务 |
| JWT | PyJWT 或 python-jose | 采用成熟密码库完成签发与验证 |
| 密码哈希 | pwdlib/Argon2 或 passlib | 不存储明文密码 |
| 后台任务 | Celery + Redis | 生产环境可靠执行；MVP 可暂用 BackgroundTasks |
| 测试 | pytest、pytest-asyncio、httpx | 单元、接口和流式集成测试 |
| 代码质量 | Ruff、mypy | 格式、Lint 和静态类型检查 |

`BackgroundTasks` 仅适合单机 MVP：进程退出时任务可能丢失，也不提供可靠重试。进入部署或演示稳定阶段后，应切换为 Celery/Redis 等持久任务队列。

## 4. 推荐工程目录

```text
backend/
  app/
    main.py
    api/
      dependencies.py
      error_handlers.py
      routers/
        auth.py
        sessions.py
        messages.py
        user_cases.py
        chat.py
        internal_rag.py
        health.py
    core/
      config.py
      security.py
      logging.py
      exceptions.py
      constants.py
    db/
      base.py
      session.py
      models/
        user.py
        chat_session.py
        chat_message.py
        user_case.py
        checkpoint_job.py
      repositories/
        users.py
        sessions.py
        messages.py
        cases.py
    schemas/
      auth.py
      session.py
      message.py
      case.py
      chat.py
      rag.py
      sse.py
    services/
      auth_service.py
      session_service.py
      case_service.py
      context_builder.py
      agent_client.py
      stream_collector.py
      knowledge_service.py
      compaction_service.py
    tasks/
      celery_app.py
      compaction_worker.py
    prompts/
      legal_checkpoint.md
    middleware/
      request_id.py
      access_log.py
      rate_limit.py
  migrations/
  tests/
    unit/
    integration/
    e2e/
  alembic.ini
  pyproject.toml
  .env.example
  Dockerfile
```

分层约束：Router 只做协议转换和依赖注入；Service 承担业务流程；Repository 只处理持久化；ORM Model 不直接作为 API 响应返回。

## 5. PostgreSQL 数据设计

### 5.1 持久化策略

推荐将消息从 `chat_sessions.messages JSONB` 拆成独立的 `chat_messages` 表。独立消息表更适合：

- 按顺序追加和分页；
- 按 `checkpoint_index` 切片；
- 保存 Tool、Usage 和错误状态；
- 并发写入控制；
- 审计、统计和后续迁移。

“双轨制”是指：

1. `chat_messages` 保存可审计的原始尾部消息，包括瘦身后的 Tool 结果；
2. `chat_sessions` 保存历史压缩后的 `checkpoint_summary` 和覆盖位置。

历史消息不应在生成 Checkpoint 后立即物理删除。Checkpoint 只改变 Agent 上下文读取范围，前端历史展示仍可从完整消息表获取。

### 5.2 `users`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `email` | VARCHAR | 唯一索引，规范化后存储 |
| `password_hash` | VARCHAR | 密码哈希 |
| `status` | VARCHAR | `active/disabled` |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

### 5.3 `chat_sessions`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `user_id` | UUID | 外键，必须建立组合查询索引 |
| `title` | VARCHAR | 会话标题 |
| `active_case_id` | UUID NULL | 当前绑定案件，可为空 |
| `status` | VARCHAR | `active/archived/deleted` |
| `checkpoint_summary` | TEXT NULL | 结构化历史摘要 |
| `checkpoint_index` | BIGINT | 已压缩到的消息序号，默认 0 |
| `checkpoint_version` | INTEGER | 乐观并发控制，默认 0 |
| `last_message_index` | BIGINT | 当前会话最后消息序号 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 最近活跃时间 |

### 5.4 `chat_messages`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `session_id` | UUID | 会话外键 |
| `user_id` | UUID | 冗余租户键，强化隔离与查询 |
| `message_index` | BIGINT | 会话内严格递增 |
| `turn_id` | UUID | 同一轮 User/Tool/Assistant 的关联 ID |
| `role` | VARCHAR | `user/tool/assistant/system` |
| `content` | TEXT | 消息正文或 Tool 瘦身文本 |
| `status` | VARCHAR | `pending/completed/failed/cancelled` |
| `tool_name` | VARCHAR NULL | Tool 消息使用 |
| `tool_call_id` | VARCHAR NULL | 对应 Node Tool Call |
| `metadata` | JSONB | 引用、模型、Usage 等非核心字段 |
| `created_at` | TIMESTAMPTZ | 创建时间 |

必须建立唯一约束 `(session_id, message_index)`，并为 `(user_id, session_id, message_index)` 建立索引。

### 5.5 `user_cases`

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `user_id` | UUID | 所属用户 |
| `name` | VARCHAR | 展示名称，不作为唯一定位依据 |
| `summary` | TEXT | 案件概要 |
| `content` | TEXT | 用户录入的案件材料 |
| `structured_facts` | JSONB | 当事人、时间线、金额、争议点等 |
| `status` | VARCHAR | `active/archived` |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

案件名称可能重复，`@案件` 最终必须解析为唯一 `case_id`，不能仅凭名称查询并自动选中。

### 5.6 可选的 `checkpoint_jobs`

生产环境建议保存压缩任务状态：`session_id`、目标 `from_index/to_index`、任务状态、重试次数、错误、摘要模型和时间。它可用于幂等、排错及避免同一会话重复压缩。

## 6. 五大核心模块设计

### 6.1 用户与会话管理

#### 6.1.1 鉴权流程

1. 注册时规范化邮箱并安全哈希密码；
2. 登录成功后签发短期 Access Token；
3. API 依赖从 `Authorization: Bearer <token>` 验证签名、过期时间、Issuer 和 Audience；
4. 从 Token 的 `sub` 获取可信 `user_id`；
5. 查询用户状态，禁用用户不能继续访问；
6. 后续 Repository 查询必须同时携带 `user_id` 和资源 ID。

客户端提交的 `userId` 永远不能作为授权依据。即使路径中提供了 `session_id` 或 `case_id`，也必须执行 `WHERE id = :id AND user_id = :current_user_id`。

#### 6.1.2 对外接口

| 方法与路径 | 作用 | 关键规则 |
| --- | --- | --- |
| `POST /api/auth/register` | 注册 | 邮箱唯一、密码强度与限流 |
| `POST /api/auth/login` | 登录 | 返回 Token，不泄露账户是否存在的细节 |
| `GET /api/sessions` | 会话列表 | 当前用户、分页、默认排除 deleted |
| `POST /api/sessions` | 新建会话 | 可选绑定 `active_case_id`，需校验归属 |
| `GET /api/sessions/{id}` | 会话详情 | 只返回当前用户数据 |
| `PATCH /api/sessions/{id}` | 改标题/案件/状态 | 状态白名单校验 |
| `DELETE /api/sessions/{id}` | 归档或软删除 | 默认不物理删除审计数据 |
| `GET /api/sessions/{id}/messages` | 前端历史消息 | 分页，只返回 User/Assistant |

前端历史接口默认过滤 `tool` 和内部 `system` 消息，但应保留引用摘要、模型信息等允许展示的 Assistant `metadata`。全量消息仅供内部上下文构建和授权审计使用。

建议响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "role": "assistant",
      "content": "……",
      "status": "completed",
      "citations": [],
      "createdAt": "2026-08-29T10:00:00Z"
    }
  ],
  "nextCursor": null
}
```

### 6.2 双轨持久化与上下文切片

#### 6.2.1 `ContextBuilder` 输入

- 当前可信 `user_id`；
- `session_id`；
- 本轮 `prompt`；
- 显式 `active_case_id`；
- 最近消息轮数或 Token 预算；
- `request_id/turn_id`。

#### 6.2.2 构建步骤

1. 按 `user_id + session_id` 读取会话；
2. 校验会话未删除；
3. 确定本轮案件作用域并按 `user_id + case_id` 校验案件；
4. 读取 `checkpoint_summary` 和 `checkpoint_index`；
5. 查询 `message_index > checkpoint_index` 的消息；
6. 以 Token 预算为主、最近 N 轮为兜底从尾部截取；
7. 保持完整 Turn，不从一轮中间截断 User/Tool/Assistant；
8. 将 Tool 消息保留给 Agent，但其内容必须已由 Node.js 瘦身；
9. 仅注入当前案件资料；
10. 生成发往 Node.js 的严格 Pydantic Payload。

若 Checkpoint 之后的消息仍超过预算，应优先保留：当前用户问题、当前案件、最近完整对话、已引用法条和未解决问题。不能悄悄截断当前案件的关键字段；发生截断时应写入内部元数据和日志。

#### 6.2.3 Python → Node.js Payload

```json
{
  "requestId": "uuid",
  "turnId": "uuid",
  "sessionId": "uuid",
  "checkpointSummary": "历史结构化摘要",
  "history": [
    {
      "index": 21,
      "role": "user",
      "content": "……"
    },
    {
      "index": 22,
      "role": "tool",
      "name": "search_legal_kb",
      "content": "瘦身结果"
    },
    {
      "index": 23,
      "role": "assistant",
      "content": "……"
    }
  ],
  "prompt": "用户本轮问题",
  "referencedCases": [
    {
      "caseId": "uuid",
      "name": "张三案",
      "summary": "……",
      "content": "……",
      "structuredFacts": {}
    }
  ]
}
```

`user_id` 原则上不需要传给 Node.js 推理层；如内部 Tool 鉴权或审计确实需要，应传递不可伪造的服务侧上下文，不允许 Node.js 使用前端原始字段。

#### 6.2.4 单轮消息落盘

推荐采用 `turn_id` 和状态字段处理流式请求：

1. 开流前写入 `user` 消息，状态为 `completed`；
2. 同时创建 Assistant 占位记录，状态为 `pending`；
3. Python 在内存中收集 Node.js 的 Tool 瘦身结果、完整 Assistant 文本和 Usage；
4. 收到合法 `done` 后，在一个数据库事务中写入 Tool 消息、完成 Assistant 记录、更新会话最后消息序号和时间；
5. 超时、取消或错误时，将 Assistant 标记为 `failed/cancelled`，不要伪装为完整答案；
6. 重试请求携带 `Idempotency-Key` 或复用 `turn_id`，避免重复写入同一轮。

不要等 SSE 完全结束后才保存用户问题，否则客户端断开时会丢失用户已提交的输入；也不要每个 Token 都写数据库，否则会造成高频写入和部分文本污染。

### 6.3 Checkpoint 后台压缩

#### 6.3.1 触发条件

每次成功完成一轮落盘后检查未压缩区间：

- 完整对话达到 15～20 轮；或
- 估算 Token 达到约 12,000；或
- 构建上下文时已接近模型预算。

阈值必须配置化。轮数是快速兜底，Token 预算是主要依据。

#### 6.3.2 压缩范围

保留最近约 10 轮原始对话，将较旧的完整 Turn 纳入新 Checkpoint。例如当前有 25 轮，可将第 1～15 轮压缩，保留第 16～25 轮。压缩边界只能位于完整 Turn 末尾。

增量压缩输入为：

- 旧 `checkpoint_summary`；
- `checkpoint_index` 之后、目标压缩位置之前的消息；
- 当前案件标识；
- 法律专属摘要 Schema。

#### 6.3.3 摘要结构

建议要求模型输出可校验 JSON，再格式化存储：

```json
{
  "parties": [],
  "confirmedFacts": [],
  "unconfirmedClaims": [],
  "timeline": [],
  "amounts": [],
  "disputes": [],
  "citedLaws": [],
  "toolFindings": [],
  "openQuestions": [],
  "userIntent": ""
}
```

摘要必须区分已确认事实、当事人陈述和模型推断；法条需保留来源 ID；不得用摘要生成新的法律事实。

#### 6.3.4 并发与幂等

同一会话可能连续触发多个后台任务，因此更新时必须：

1. 记录任务开始时的 `checkpoint_index/version`；
2. 为目标压缩区间生成唯一任务键；
3. 使用行锁或乐观锁比较版本；
4. 只在数据库仍处于预期版本时更新摘要和索引；
5. 重复任务直接返回成功，不重复推进；
6. 失败时有限重试，不能阻塞正常聊天。

Checkpoint 失败时退化为原始滑动窗口，不影响本轮回答。

### 6.4 知识库与用户案件

#### 6.4.1 内部 RAG 接口

`POST /internal/knowledge/search` 仅对 Node.js 内网服务开放，不使用普通用户 JWT。推荐采用私网访问加服务身份认证，例如内部 Token 或 mTLS，并设置调用方、超时、查询长度和并发限制。

请求示例：

```json
{
  "requestId": "uuid",
  "query": "盗窃罪数额较大的认定标准",
  "topK": 8,
  "filters": {
    "documentTypes": ["law", "case"],
    "jurisdiction": "CN"
  }
}
```

响应示例：

```json
{
  "query": "盗窃罪数额较大的认定标准",
  "results": [
    {
      "sourceId": "Law-264",
      "sourceType": "law",
      "title": "中华人民共和国刑法第二百六十四条",
      "content": "原始命中文本",
      "score": 0.91,
      "metadata": {
        "effectiveDate": "……"
      }
    }
  ],
  "tookMs": 35
}
```

Python 可返回 Node.js Tool 所需的较完整检索结果，由 Node.js 在 Tool 内进行上下文瘦身；但“全量原始 JSON”仍须设置硬上限，包括 `topK`、单文档字符数和总响应字节数，防止知识服务异常返回导致内存和 Token 失控。

#### 6.4.2 知识服务适配层

`KnowledgeService` 屏蔽具体实现，统一暴露 `search(query, top_k, filters)`。MVP 可先使用 Mock/PGVector，后续切换 Milvus、Elasticsearch 或外部 API 时不修改 Router 和 Agent 契约。

知识库连接使用只读凭证。接口不得暴露插入、删除、索引重建或任意 SQL 能力。

#### 6.4.3 用户案件接口

| 方法与路径 | 作用 |
| --- | --- |
| `GET /api/cases` | 当前用户案件列表 |
| `POST /api/cases` | 新建案件 |
| `GET /api/cases/{id}` | 获取案件详情 |
| `PATCH /api/cases/{id}` | 更新案件内容或结构化事实 |
| `DELETE /api/cases/{id}` | 归档案件 |

前端选择 `@张三案` 后应提交已解析的唯一 `activeCaseId/caseId`。Python 校验归属后将案件内容注入 `referencedCases`。如果文本标记与 ID 不一致、案件不存在或不属于当前用户，应拒绝请求，不能回退到模糊猜测。

### 6.5 SSE 代理网关

#### 6.5.1 对外聊天接口

`POST /api/chat` 请求示例：

```json
{
  "sessionId": "uuid",
  "prompt": "请分析本案可能涉及的法律责任",
  "activeCaseId": "uuid"
}
```

Header 至少包含：

- `Authorization: Bearer <JWT>`；
- `Accept: text/event-stream`；
- 可选 `Idempotency-Key`。

#### 6.5.2 标准执行流程

```text
前端 POST /api/chat
  → JWT 校验、限流、生成 request_id/turn_id
  → 校验 session 和 active_case 的用户归属
  → 写入 User 消息与 pending Assistant
  → ContextBuilder 组装 Payload
  → httpx.AsyncClient.stream 调用 Node /agent/run
  → 逐个解析 Node SSE 事件
  → 合法事件规范化后立即转发给前端
  → 同时收集 Tool、Assistant 完整文本和 Usage
  → 收到 done 后事务落盘
  → 提交 Checkpoint 检测任务
```

#### 6.5.3 SSE 事件契约

建议统一使用具名事件：

```text
event: message_start
data: {"requestId":"...","turnId":"..."}

event: token
data: {"delta":"本"}

event: tool_start
data: {"toolCallId":"...","name":"search_legal_kb"}

event: tool_result
data: {"toolCallId":"...","name":"search_legal_kb","content":"瘦身结果"}

event: usage
data: {"inputTokens":1000,"outputTokens":300}

event: done
data: {"finishReason":"stop"}
```

Python 不建议进行完全不解析的字节级盲转发，因为它需要识别 `tool_result`、`usage`、`done` 和 `error` 来完成落盘与异常处理。正确做法是：**增量解析、校验事件、立即转发，并同步收集持久化所需数据**。这不会引入人为缓冲，只会增加可忽略的协议处理开销。

#### 6.5.4 断开与异常处理

- 前端断开：取消 `httpx` 下游流，Assistant 标记 `cancelled`；
- Node.js 连接失败：返回结构化 `error` 事件，Assistant 标记 `failed`；
- Node.js 流中断且无 `done`：不能落为完整回答；
- Tool 失败：由 Node.js 决定是否继续推理，Python记录错误事件；
- 数据库最终提交失败：记录高优先级错误并进入补偿/重试队列；
- 超时：连接超时、首事件超时和整轮最大时长分别配置；
- SSE 响应设置禁止代理缓冲的 Header，并定期发送心跳注释避免空闲连接被关闭。

面向用户的错误信息应稳定、友好且不暴露内部 URL、堆栈、数据库语句或模型密钥。

## 7. API 错误规范

REST 错误统一格式：

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "会话不存在或无权访问",
    "requestId": "uuid"
  }
}
```

为避免资源枚举，跨租户访问通常也返回 404，而不是明确告知资源属于其他用户。

SSE 建立后无法再修改 HTTP 状态码，因此流内错误使用：

```text
event: error
data: {"code":"AGENT_TIMEOUT","message":"生成超时，请稍后重试","retryable":true,"requestId":"..."}
```

## 8. 配置项

`.env.example` 至少声明：

```text
APP_ENV=
APP_HOST=
APP_PORT=
DATABASE_URL=
JWT_SECRET=
JWT_ALGORITHM=
JWT_ISSUER=
JWT_AUDIENCE=
ACCESS_TOKEN_EXPIRE_MINUTES=
AGENT_ENGINE_BASE_URL=
AGENT_ENGINE_SERVICE_TOKEN=
AGENT_CONNECT_TIMEOUT_SECONDS=
AGENT_READ_TIMEOUT_SECONDS=
AGENT_MAX_STREAM_SECONDS=
KNOWLEDGE_BACKEND=
KNOWLEDGE_READONLY_DSN=
REDIS_URL=
CHECKPOINT_TRIGGER_TURNS=
CHECKPOINT_TRIGGER_TOKENS=
CHECKPOINT_KEEP_RECENT_TURNS=
CONTEXT_MAX_TOKENS=
LOG_LEVEL=
```

真实密钥不得提交到仓库。配置启动时应强校验，生产环境不能使用默认 JWT Secret。

## 9. 可观测性

Python 与 Node.js 必须共享同一 `request_id`，每条核心日志至少包含：

- `request_id`、`turn_id`；
- 脱敏后的 `user_id`；
- `session_id`、`active_case_id`；
- 路由、状态码和总耗时；
- 上下文消息数和估算 Token；
- Node 首 Token 延迟和流总时长；
- Tool 名称、查询耗时和结果数；
- 模型与 Usage；
- Checkpoint 的起止 Index、版本和任务状态。

普通日志不得输出完整 Prompt、案件正文、知识库原文、JWT 或密码。需要审计时使用受控审计存储，并定义保留周期和访问权限。

## 10. 测试计划

### 10.1 单元测试

- JWT 签发、过期、Issuer/Audience 和禁用用户；
- 所有 Repository 的 `user_id` 隔离；
- 上下文从 `checkpoint_index` 后读取；
- Token 预算和完整 Turn 截断；
- Tool 消息对前端过滤、对 Agent 保留；
- 案件 ID 归属和名称重复；
- SSE 增量解析及完整文本收集；
- Checkpoint Schema 校验、边界和版本冲突。

### 10.2 集成测试

- FastAPI + PostgreSQL 的迁移和事务；
- Mock Node.js SSE 的正常、错误、超时、中断事件；
- Mock 知识库的空结果、超长结果和不可用；
- 重复 `Idempotency-Key` 不重复落盘；
- 并发 Checkpoint 任务只能有一个成功推进版本。

### 10.3 端到端验收场景

1. 用户登录并创建会话；
2. 创建两个案件并分别对话；
3. 验证每次 Payload 只出现当前案件；
4. 连续多轮聊天并刷新恢复历史；
5. 前端历史中不显示 Tool，Agent 上下文中存在瘦身 Tool；
6. 客户端中途停止生成，Node 请求被取消且数据库状态正确；
7. 达到阈值后异步生成 Checkpoint；
8. 服务重启后使用摘要和尾部消息继续对话；
9. 用户 A 构造用户 B 的 session/case ID 时无法读取；
10. Node.js 或知识库异常时前端收到统一错误且服务可继续使用。

## 11. 开发顺序与里程碑

原建议把鉴权放在后期补齐，但只要接口开始访问用户会话和案件，最小鉴权与租户隔离就属于前置依赖。推荐按以下顺序实施。

### P0：工程与数据基座

- 创建 FastAPI 工程、配置、日志、健康检查；
- 建立 SQLAlchemy Async 和 Alembic；
- 创建 users、sessions、messages、cases 表；
- 实现最小 JWT 依赖和 Repository 租户过滤。

**验收**：服务可启动、迁移可重复执行、用户隔离测试通过。

### P1：会话、消息与案件 CRUD

- 完成 Session 和 Case API；
- 完成前端历史消息查询并过滤 Tool；
- 实现消息顺序、Turn 状态和事务写入。

**验收**：可创建案件/会话、写入消息、分页恢复历史且不跨租户。

### P2：内部 RAG

- 实现 `KnowledgeService` 抽象和 Mock；
- 实现 `/internal/knowledge/search`；
- 加入服务认证、只读配置、结果大小限制；
- 与 Node.js Tool 单点联调。

**验收**：Node.js 能用真实接口替换 Mock，并拿到稳定结构结果。

### P3：上下文与 SSE 主链路

- 实现 `ContextBuilder`；
- 固定最近 10 轮作为首版策略；
- 实现 `AgentClient` 和 `/api/chat`；
- 解析、转发并收集 SSE；
- 实现成功、失败、取消和幂等落盘。

**验收**：完成“前端请求 → Python → Node.js → Python → 前端 → PostgreSQL”的多轮闭环。

### P4：案件强绑定

- 对接前端 `ActiveCaseId/@案件`；
- 严格案件归属校验；
- Payload 只注入当前案件；
- 增加双案件防串案测试。

**验收**：切换、刷新和并发请求均不发生案件上下文污染。

### P5：Checkpoint

- 实现 Token/轮数监控；
- 编写法律摘要 Prompt 和结构化输出 Schema；
- MVP 使用 BackgroundTasks 验证；
- 稳定部署前迁移 Celery/Redis；
- 加入版本锁、幂等和失败降级。

**验收**：长会话上下文受控、摘要关键事实不丢失、压缩失败不影响聊天。

### P6：生产加固

- 限流、服务认证、超时、重试和熔断；
- 指标、Tracing、告警和审计；
- 压测 SSE、连接池和后台任务；
- 安全扫描、日志脱敏和密钥托管。

**验收**：达到约定并发、延迟、错误率和安全基线。

## 12. Stage 2 完成定义（Definition of Done）

Python 层满足以下条件后，可认为 Stage 2 主体完成：

- FastAPI 工程可以通过配置独立启动；
- Alembic 可从空数据库创建全部业务表；
- JWT 校验和所有资源的租户隔离测试通过；
- 会话、消息、案件 CRUD 可用；
- 前端历史查询隐藏 Tool，Agent 上下文保留瘦身 Tool；
- `/internal/knowledge/search` 只读、受服务认证保护并有限流/大小限制；
- `/api/chat` 能稳定代理 Node.js SSE；
- User、Tool、Assistant、Usage 按 Turn 正确持久化；
- 客户端断开、Node 超时和流异常的数据库状态正确；
- `ActiveCaseId` 显式绑定且多案件不串号；
- Checkpoint 能异步、幂等地推进且失败可降级；
- 核心单元与集成测试进入自动化执行；
- 日志可按 `request_id` 串联 Python、Node.js 和知识检索链路。

## 13. 第一批实际开发任务

当前项目仍以设计文档为主，建议第一批提交严格限制在以下范围：

1. 创建 `backend/` FastAPI 工程骨架；
2. 配置 SQLAlchemy Async、asyncpg 和 Alembic；
3. 建立 `users/chat_sessions/chat_messages/user_cases` 模型和首个迁移；
4. 实现 `get_current_user` JWT 依赖；
5. 实现按 `user_id + session_id` 写入消息；
6. 实现按 `checkpoint_index` 获取最近 10 轮完整 Turn；
7. 为数据隔离和上下文切片编写测试。

完成这一批后，Python 层就具备可验证的数据基座，可以继续接入内部 RAG 和 Node.js SSE，而不会在主链路完成后再返工权限与消息模型。
