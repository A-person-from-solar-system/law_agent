# 政企法律 Agent 前端开发需求（Dev Stage 3）

## 1. 文档定位

本文是 `dev_stage1.md`（Node.js Agent Engine）与 `dev_stage2.md`（FastAPI 业务中台）之后的前端专项实施文档，用于指导当前项目完成可演示、可联调、可持续迭代的政企法律 Agent Web 客户端。

Stage 3 的核心目标不是单纯制作聊天页面，而是建立一层稳定的交互适配层：对用户隐藏 Agent 推理、Tool 调用、SSE 代理、案件注入和会话持久化等后端细节，同时保留必要的过程反馈、法律依据和错误恢复能力。

本文以当前仓库已经实现的接口为准，不以理想化接口替代现状。前端只访问 FastAPI `mid-layer`，不得直接调用 Node.js `agent-engine` 或内部知识库接口。

## 2. 阶段目标与非目标

### 2.1 Stage 3 必须完成

1. 员工号登录、首次强制改密、登录态恢复和退出登录；
2. 会话列表、新建会话、切换会话、修改标题和删除会话；
3. 历史消息分页加载，只呈现 User/Assistant 消息；
4. 基于 `fetch` 的 POST SSE 流式聊天；
5. Tool 运行状态、流式文本、停止生成、失败和重试交互；
6. Markdown、GFM 表格、引用块和安全链接渲染；
7. `@案件` 检索、案件 Chip 和 `active_case_id` 显式提交；
8. 案件的新建、查看、编辑、归档/删除管理；
9. 智能自动滚动、移动端适配、基础无障碍支持；
10. 单元测试、组件测试和关键链路端到端测试。

### 2.2 本阶段不包含

- 前端直接执行 RAG、Embedding、模型推理或 Tool；
- 展示模型内部思维链、完整 Tool 原始 JSON 或系统提示词；
- 富文本案件卷宗协同编辑、OCR、批量文件上传；
- 多案件同时注入同一轮推理；
- WebSocket 实时协作；
- 离线模式或跨设备本地消息同步；
- 面向公网的支付、计费和组织级 RBAC 管理后台。

## 3. 技术选型与工程约束

本阶段统一采用 React 技术栈，避免同时维护 React/Vue 两套方案。

| 领域 | 选型 | 约束 |
| --- | --- | --- |
| 框架 | Next.js + React + TypeScript | 使用 App Router；聊天主界面为 Client Component |
| 样式 | Tailwind CSS + shadcn/ui | 统一设计 Token，不散落魔法颜色和尺寸 |
| 服务端数据 | TanStack Query | 管理用户、会话、案件和历史消息缓存 |
| 临时 UI 状态 | 组件局部 State，必要时 Zustand | 流式 Token 禁止进入全局 Store |
| 表单 | React Hook Form + Zod | 表单和 API 边界均执行校验 |
| Markdown | react-markdown + remark-gfm | 禁止直接使用 `dangerouslySetInnerHTML` |
| 输入框 | 第一版原生 textarea + 自研 Mention Popover | 不为单个 `@案件` 功能引入重型编辑器 |
| 测试 | Vitest + Testing Library + Playwright | 覆盖 SSE 分片、滚动、案件绑定和中止 |

推荐目录：

```text
frontend/
  app/
    (auth)/
      login/page.tsx
      change-password/page.tsx
    (workspace)/
      chat/[sessionId]/page.tsx
      cases/page.tsx
    layout.tsx
    providers.tsx
  components/
    auth/
    chat/
      chat-shell.tsx
      message-list.tsx
      message-bubble.tsx
      streaming-message.tsx
      tool-activity.tsx
      chat-composer.tsx
      case-mention-popover.tsx
      case-chip.tsx
      scroll-to-bottom.tsx
    cases/
      case-list.tsx
      case-form.tsx
      case-detail-drawer.tsx
    legal/
      legal-markdown.tsx
      legal-reference.tsx
  lib/
    api/
      client.ts
      auth.ts
      sessions.ts
      cases.ts
      chat.ts
      contracts.ts
    sse/
      parser.ts
      reducer.ts
      types.ts
    auth/
      token-store.ts
    errors/
      normalize-error.ts
  hooks/
    use-chat-stream.ts
    use-smart-scroll.ts
    use-case-mention.ts
  tests/
    unit/
    component/
    e2e/
  .env.example
  package.json
```

所有 API 字段转换集中在 `lib/api`。后端当前使用 `snake_case`，前端组件内部可使用 `camelCase`，但禁止在各组件内临时手写转换。

## 4. 页面与信息架构

### 4.1 员工登录与首次改密页

- 系统不开放员工自助注册，员工账号由管理员统一创建；
- 登录字段为 `employee_no`（6～10 位数字员工号）和密码，邮箱仅作为可选员工资料，不参与登录；
- 管理员创建员工后生成一次性初始密码，登录响应通过 `requires_password_change` 标识是否必须改密；
- 首次登录必须跳转 `/change-password`，输入当前临时密码、新密码和确认密码；
- 新密码至少 12 位并同时包含字母和数字，前端先校验，后端仍是最终校验方；
- 完成改密前不得进入会话、案件等业务页面；
- 正常登录成功后请求 `/api/auth/me` 验证身份并进入最近会话；
- 员工连续登录失败可能收到 `ACCOUNT_LOCKED`，前端展示后端文案且不自动重试；
- 401 时清理无效凭证并返回登录页；
- 错误提示使用后端 `error.message`，不得展示响应堆栈或原始异常对象。

### 4.2 聊天工作台

桌面端采用三段式布局：左侧会话栏、中间对话区、可选右侧案件信息抽屉。移动端将会话栏和案件详情改为 Drawer。

聊天区必须包含：

- 当前会话标题；
- 当前绑定案件状态；
- 历史消息列表；
- Tool 过程提示；
- 当前流式消息；
- `@案件` 输入框；
- 发送/停止按钮；
- 回到底部按钮；
- 空会话引导和常用法律问题示例。

### 4.3 案件库页

- 案件列表支持按名称前端过滤；
- 明确区分 active、archived 状态；
- 支持新建、编辑、查看和删除；
- 表单字段对应后端 `name`、`summary`、`content`、`structured_facts`；
- 第一版 `structured_facts` 提供结构化表单或合法 JSON 编辑区，提交前必须校验为对象；
- 删除属于后端软删除，UI 中仍需二次确认并明确其会从 `@案件` 列表消失。

## 5. 当前后端 API 契约

API Base URL 通过 `NEXT_PUBLIC_API_BASE_URL` 配置。除登录外，所有请求必须携带：

```http
Authorization: Bearer <access_token>
```

### 5.1 鉴权

| 方法 | 路径 | 请求/响应 |
| --- | --- | --- |
| POST | `/api/auth/login` | `{ employee_no, password }` → `{ access_token, token_type, requires_password_change }` |
| POST | `/api/auth/change-password` | `{ current_password, new_password }` → 204 |
| GET | `/api/auth/me` | → 当前 User |

当前用户响应包含 `employee_no`、`name`、可选 `email`、`role`、`status`、`must_change_password` 和密码过期信息。侧栏应优先展示员工姓名与员工号，不再把邮箱作为主身份。

当前后端只返回 Access Token，尚无 Refresh Token。前端遇到 401 时退出登录，不实现伪刷新机制。若采用 `localStorage` 存 Token，需明确其 XSS 风险；生产方案应优先由后端增加 HttpOnly、Secure、SameSite Cookie 或短期 Access Token + Refresh Token 机制。前端路由保护还必须检查 `must_change_password`：该值为 true 时只允许访问改密页和退出登录。

### 5.2 会话与消息

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/sessions` | 获取当前用户未删除会话，按更新时间倒序 |
| POST | `/api/sessions` | `{ title, active_case_id? }` |
| GET | `/api/sessions/{session_id}` | 获取会话详情 |
| PATCH | `/api/sessions/{session_id}` | 更新 `title`、`active_case_id` 或 `status` |
| DELETE | `/api/sessions/{session_id}` | 软删除，成功响应 204 |
| GET | `/api/sessions/{session_id}/messages?cursor=&limit=` | 历史消息游标分页 |

历史响应为：

```json
{
  "items": [
    {
      "id": "uuid",
      "role": "assistant",
      "content": "回答正文",
      "status": "completed",
      "metadata": { "usage": {} },
      "created_at": "2026-08-29T10:00:00Z"
    }
  ],
  "next_cursor": 21
}
```

后端已过滤 `tool` 和 `system`。前端仍需对 `role` 做白名单保护，只渲染 `user` 和 `assistant`。接口按旧到新返回当前页；向上加载更早页时，应保持视口锚点，禁止列表突然跳到底部。

### 5.3 案件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/cases` | 当前用户未删除案件 |
| POST | `/api/cases` | 新建案件 |
| GET | `/api/cases/{case_id}` | 案件详情 |
| PATCH | `/api/cases/{case_id}` | 更新案件或状态 |
| DELETE | `/api/cases/{case_id}` | 软删除 |

案件名称不是唯一键。Mention 选中项必须保存唯一 `id`，提交聊天时只能传 ID，不得把案件名称当作绑定依据。

### 5.4 REST 错误

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "会话不存在或无权访问",
    "requestId": "req-...",
    "details": []
  }
}
```

API Client 应统一转换为 `ApiError`，至少保存 `status`、`code`、`message`、`requestId` 和可选 `details`。未知错误使用稳定的兜底文案。

## 6. SSE 流式聊天需求

### 6.1 请求方式

当前聊天接口为带 JSON Body 和 Bearer Token 的 `POST /api/chat`，因此不能使用只支持 GET 且难以设置 Authorization Header 的原生 `EventSource`。必须使用 `fetch` + `ReadableStream`：

```json
{
  "session_id": "uuid",
  "prompt": "请分析本案可能涉及的法律责任",
  "active_case_id": "uuid-or-null"
}
```

Header 至少包含：

- `Authorization: Bearer <token>`；
- `Accept: text/event-stream`；
- `Content-Type: application/json`；
- 客户端生成的 `X-Request-ID`，用于排障关联。

### 6.2 SSE 解析器

解析器必须正确处理：

- 任意网络分片，不能假设一次 `read()` 就是一条事件；
- `\r\n` 和 `\n`；
- 多行 `data:`；
- `:` 开头的心跳注释；
- UTF-8 中文跨字节分片，`TextDecoder.decode(..., { stream: true })`；
- 未知事件向前兼容地忽略并记录开发日志；
- JSON 解析失败转为 `INVALID_SSE_EVENT`，保留已生成文本。

禁止通过简单的 `chunk.split("\n\n")` 独立处理每个网络 Chunk，因为事件边界可能跨 Chunk。

### 6.3 当前事件契约

| 事件 | 关键数据 | 前端行为 |
| --- | --- | --- |
| `run.started` | `requestId`, `sessionId` | 状态切换为 generating |
| `text.delta` | `requestId`, `delta` | 追加到局部缓冲区 |
| `tool.started` | `toolCallId`, `toolName` | 显示“正在检索相关法律资料…” |
| `tool.completed` | `toolCallId`, `toolName`, `isError`, `result` | 标记完成/失败，默认不展示原始 result |
| `usage` | Token 统计 | 仅存调试/统计，不抢占主 UI |
| `run.completed` | `finalMessage`, `newMessages` | 完成本轮、刷新历史与会话缓存 |
| `run.failed` | `code`, `message`, 可选 `retryable` | 保留部分文本并展示错误与重试入口 |
| `checkpoint.pending` | `requestId`, `sessionId` | 内部状态，可静默忽略 |

前端必须采用事件白名单和运行状态机，不能将事件名直接映射为任意组件或 HTML。

建议状态机：

```text
idle → connecting → generating → completed
                   ↘ failed
                   ↘ cancelled
```

单个会话同一时间只允许一个前端生成任务。生成期间禁用重复发送，但输入框内容可以继续编辑为下一问。

### 6.4 平滑打字机渲染

网络接收文本与视觉渲染文本分离：

1. SSE 回调只将 `delta` 追加到 `useRef` 缓冲；
2. 使用 `requestAnimationFrame` 或约 30～50ms 定时批量提交到 `StreamingMessage` 的局部 State；
3. 流结束时立即冲刷剩余缓冲；
4. 仅当前 `StreamingMessage` 重渲染，侧栏、输入框和历史消息不随 Token 更新；
5. 完成后再将最终消息交给 Query Cache，卸载临时组件。

不得对逐 Token 文本执行完整页面级 Markdown 解析。流式阶段可节流解析或先安全渲染轻量 Markdown，完成后再执行完整 GFM 渲染。

### 6.5 停止生成

- 每次发送创建独立 `AbortController`；
- “停止生成”调用 `abort()`，立即关闭读取流；
- UI 状态变为 cancelled，保留当前可见文字并标注“已停止生成”；
- 组件卸载、切换会话、退出登录时必须取消未完成请求；
- `AbortError` 不显示为系统故障 Toast；
- 当前后端通过客户端断开感知取消，没有单独的 cancel API，前端不得声称服务端已百分之百停止计费，只能表示“已发送停止请求”。

### 6.6 失败与重试

- 流建立前 HTTP 非 2xx：读取 REST 错误体；
- 流建立后的 `run.failed`：使用事件中的稳定文案；
- 网络断开且未收到 `run.completed`：保留部分回答，显示“连接中断，当前进度已保留”；
- “重新生成”重新发送原 Prompt、原 `session_id` 和原 `active_case_id`；
- 未实现幂等接口前，网络状态不明时不得自动静默重试 POST，以免产生重复消息；
- 重试前建议刷新历史，确认后端是否已完成落盘。

## 7. 智能滚动与消息列表

### 7.1 自动滚动规则

- 通过底部 Sentinel + `IntersectionObserver` 判断用户是否接近底部；
- 用户位于底部时，流式更新随内容向下滚动；
- 用户主动上滑超过阈值后暂停自动滚动；
- 暂停期间显示“回到底部”悬浮按钮，可附未读更新提示；
- 用户重新到达底部后恢复自动滚动；
- 首次进入会话加载完成后定位到最新消息，不播放冗长滚动动画；
- 向上加载历史时记录插入前后的 `scrollHeight` 差值并恢复视口位置。

### 7.2 消息状态

- `completed`：正常显示；
- `failed`：显示失败标识，不把空内容渲染成正常回答；
- `cancelled`：显示已停止；
- `pending`：当前后端历史接口不返回 pending，实时 UI 由本地状态表示；
- 用户消息在请求发出时乐观加入当前页面，但最终以历史接口为准去重。

消息 Key 使用后端消息 ID；本地临时消息使用带命名空间的 Client ID，并在刷新历史后通过请求上下文或内容/时间谨慎替换，不能使用数组下标。

## 8. Markdown 与法律内容渲染

### 8.1 基础渲染

- 支持标题、列表、粗体、引用、表格、行内代码和代码块；
- 表格在窄屏可横向滚动；
- 外链默认新窗口打开并设置 `rel="noopener noreferrer"`；
- 禁止原始 HTML，或使用严格白名单 Sanitizer；
- 超长连续文本和 URL 必须换行，不能撑破布局；
- 为复制回答、复制代码提供明确按钮和成功反馈。

### 8.2 法条引用组件

Stage 3 第一版仅对有可靠结构来源的数据生成可点击法条卡片。若后端只返回回答正文，前端可以对《法律名称》第 X 条做非破坏性视觉高亮，但不得仅凭正则伪造完整法条内容、效力状态或来源链接。

建议后续由 Assistant 消息 `metadata` 提供：

```json
{
  "citations": [
    {
      "sourceId": "Law-264",
      "sourceType": "statute",
      "title": "中华人民共和国刑法第二百六十四条",
      "articleNumber": "第二百六十四条",
      "excerpt": "……"
    }
  ]
}
```

在该字段落地前，法条弹窗功能标记为受后端契约阻塞，不允许前端从 Tool 原始结果中私自拼装业务事实。

## 9. `@案件` Mention 交互

### 9.1 第一版行为

1. 输入框获得焦点后键入 `@`，在光标附近打开案件列表；
2. `@` 后的文本用于按案件名称过滤；
3. 支持方向键、Enter 选择、Esc 关闭和鼠标选择；
4. 选中后显示不可编辑的案件 Chip，并保存唯一 `caseId`；
5. 每条消息最多绑定一个案件；选择新案件时替换旧案件；
6. 删除 Chip 时将 `active_case_id` 设为 null；
7. 提交时正文 `prompt` 不需要包含伪造的 `@[名称](id)` 语法，案件 ID 作为独立字段发送；
8. 当前案件被删除或归档后，发送前重新校验并要求用户选择有效案件。

### 9.2 会话案件与本轮案件

当前后端会话存在 `active_case_id`，聊天请求也接受 `active_case_id`。前端规则统一为：

- 打开会话时，以会话 `active_case_id` 初始化 Composer Chip；
- 用户在 Composer 切换案件后，先 PATCH 会话，再用于后续发送；
- 若 PATCH 失败，不得只在本地显示已绑定；
- 发送请求显式携带当前 Chip ID，避免依赖后端隐式状态；
- UI 始终显示本轮将使用的案件，防止串案。

## 10. 状态管理与缓存策略

### 10.1 TanStack Query 管理

- 当前用户；
- 会话列表与会话详情；
- 分页历史消息；
- 案件列表与详情；
- CRUD Mutation 后的精准失效和乐观更新。

### 10.2 局部状态管理

- 当前输入文本；
- Mention 是否打开和高亮索引；
- 当前 `AbortController`；
- SSE 状态机；
- Token 缓冲与流式文本；
- Tool 活动列表；
- 是否贴近底部。

禁止将逐 Token 文本写入 Zustand、Redux、Query Cache 或持久化 Storage。流完成后只执行一次正式缓存合并/刷新。

切换会话时，每个会话的草稿可按 `sessionId` 保存到 `sessionStorage`，但不得保存案件正文、完整回答或 Token。退出登录时清除用户相关缓存。

## 11. 安全、隐私与可访问性

### 11.1 安全与隐私

- 不把 JWT、案件正文、Prompt 或回答写入 Console、埋点 URL、错误上报 Breadcrumb；
- Markdown 禁止不受控 HTML、脚本协议和内联事件；
- API Base URL 由环境变量提供，不在源码硬编码生产地址；
- 401 统一清理登录态，403/404 不推断资源归属；
- 员工号不得写入 URL 或分析埋点；账号锁定、临时密码过期和强制改密均使用后端错误码驱动；
- 前端不提供公开注册入口，不保存或展示管理员生成的一次性初始密码；
- 登出时清理 Query Cache、草稿和 Token；
- 案件删除、会话删除需要确认；
- UI 固定展示“内容由 AI 生成，请结合有效法律文本和专业意见复核”的适度提示；
- 不展示 Chain-of-Thought；Tool 状态只呈现业务级摘要。

### 11.2 可访问性

- 所有交互可通过键盘完成；
- Mention 使用 Combobox/Listbox 语义；
- 流式文本区域避免每个 Token 都触发屏幕阅读器播报，可在完成后用 `aria-live="polite"` 通知；
- 按钮具有可感知名称和 Focus 样式；
- 颜色不是错误/成功状态的唯一表达；
- 正文、引用和弱化文字满足基本对比度要求；
- 尊重 `prefers-reduced-motion`。

## 12. 性能指标与工程质量

本地正常环境下的目标：

- 路由级代码拆分，案件管理组件不进入初始聊天关键包；
- 100 条消息切换会话时保持流畅；超过约 200 条时评估虚拟列表，但不得破坏动态高度和向上分页；
- Token 到达至可见文本更新的额外延迟 P95 小于 100ms；
- 流式阶段每秒 React Commit 数受批量策略控制，不随 Token 数线性增长；
- 页面无明显布局偏移，长表格和代码块不撑破主容器；
- `npm run lint`、`npm run typecheck`、`npm test` 必须通过。

## 13. 测试需求

### 13.1 单元测试

- SSE 事件跨 Chunk、中文跨字节、多行 data、心跳和尾部残片；
- 未知事件忽略、非法 JSON、`run.failed`；
- Stream Reducer 的合法与非法状态迁移；
- REST 错误归一化；
- 员工号 6～10 位纯数字校验、强密码校验和 `requires_password_change` 路由分支；
- API snake_case/camelCase 转换；
- Mention 查询解析和单案件替换；
- Markdown 链接协议与 HTML 注入防护。

### 13.2 组件测试

- `StreamingMessage` 批量刷新并在结束时冲刷；
- 用户上滑后停止自动滚动，回到底部后恢复；
- Tool 开始、完成、失败状态；
- 点击停止触发 Abort 且不显示错误 Toast；
- 案件 Chip 的选择、替换和清除；
- 历史消息过滤内部 Role；
- failed/cancelled 消息状态展示。

### 13.3 端到端测试

1. 员工号和临时密码登录后必须进入首次改密页；
2. 改密成功后进入工作台，刷新可以恢复员工身份；
3. 普通员工不能从前端自助注册账号；
4. 创建案件并通过 `@` 绑定到新会话；
5. 发送消息，依次看到 Tool 提示和流式回答；
6. 生成中上滑，验证页面不强制回底；
7. 停止生成并保留当前文本；
8. 模拟网络中断，展示可重试状态；
9. 刷新页面后从历史恢复 User/Assistant，且不显示 Tool 消息；
10. 切换两个案件，验证请求携带正确 `active_case_id`；
11. 删除案件后 Mention 列表不再出现；
12. Access Token 失效后返回登录页且不泄露旧用户缓存。

Playwright 的 SSE Mock 必须真实模拟随机分片和延时，不得只返回完整事件字符串。

## 14. 实施顺序与里程碑

### P0：前端工程与契约层

- 创建 `frontend/` Next.js TypeScript 工程；
- 配置 Tailwind、shadcn/ui、Lint、Typecheck 和测试；
- 定义 API Contract、统一 Client 和错误模型；
- 完成员工号登录、首次强制改密和路由保护，不提供自助注册。

**验收**：可使用员工号登录 FastAPI；临时密码账号只能进入改密页；401 能正确清理状态并跳转。

### P1：会话与历史消息

- 会话列表、创建、切换、改名和删除；
- 历史消息游标分页；
- 消息气泡和基础 Markdown；
- 智能滚动骨架。

**验收**：刷新和切换会话可稳定恢复干净历史，不展示 Tool。

### P2：SSE 主链路

- 实现健壮 SSE Parser；
- 实现 `useChatStream` 和状态机；
- 局部缓冲打字机、Tool 状态、停止生成；
- 完成后刷新/合并历史缓存。

**验收**：正常、Tool、失败、中断、取消五类流均有确定 UI 结果。

### P3：案件库与 `@案件`

- 案件 CRUD 页面；
- Mention Popover、Chip 和键盘交互；
- 会话 `active_case_id` 同步；
- 双案件切换防串案测试。

**验收**：UI 可明确展示并提交唯一案件 ID，刷新后绑定仍一致。

### P4：法律富文本与体验加固

- 完整 GFM、复制、表格和代码块；
- 有结构化 citation 后接入法条卡片；
- 移动端、无障碍、错误恢复和性能优化；
- Playwright 端到端测试。

**验收**：达到演示质量，并通过关键业务链路回归。

## 15. 后端联调前置项与已知缺口

以下事项应在 Stage 3 联调初期确认或补齐：

1. **CORS**：当前 `mid-layer/app/main.py` 未配置 `CORSMiddleware`。若 Next.js 与 FastAPI 不同源，后端必须明确允许前端 Origin、Authorization、Content-Type、X-Request-ID，并正确处理预检；生产环境不得使用带凭证的通配 Origin。
2. **取消语义**：当前依赖 HTTP 断开触发服务端取消，没有显式 cancel endpoint。需要集成测试确认 ASGI/反向代理能及时传播断开。
3. **幂等重试**：当前 `/api/chat` 未接收 `Idempotency-Key`。在后端支持前，前端不得自动重试状态不明的聊天 POST。
4. **引用数据**：当前历史 Assistant `metadata` 主要保存 usage，尚无稳定 citations。可点击法条原文卡片应等待引用契约落地。
5. **Token 生命周期**：当前没有 Refresh Token/HttpOnly Cookie，生产鉴权方案需另行加固；同时确认完成首次改密后原 JWT 是否继续使用，前端按当前实现保留该 Token 并重新请求 `/api/auth/me`。
6. **失败消息正文**：服务端流失败会将数据库 Assistant 标为 failed，但部分流式正文未落盘；页面刷新后可能无法恢复已生成的部分文本，UI 文案不能承诺其已永久保存。
7. **会话并发**：后端尚未声明同会话并发生成策略。前端先限制单会话单流，后端仍应增加并发保护。
8. **事件兼容**：`checkpoint.pending` 是 FastAPI 额外事件，不在 Node.js 事件联合类型内。前端需容忍该事件，后端文档需将其正式纳入外部契约。

## 16. Stage 3 完成定义（Definition of Done）

满足以下全部条件后，Stage 3 主体完成：

- `frontend/` 可通过环境变量独立启动并连接 `mid-layer`；
- 鉴权、会话、消息和案件主流程可用；
- 员工号登录、首次强制改密、账号锁定错误和无自助注册入口符合 Python 契约；
- POST SSE 在随机分片、中文内容和 Tool 事件下稳定解析；
- 流式文本只引发局部、受控频率的渲染；
- 用户上滑时不会被强制拉回底部；
- 停止生成、网络断开和 Agent 错误都有明确且可恢复的 UI；
- `@案件` 使用唯一 ID，刷新、切换和发送时不发生案件错绑；
- 历史视图只展示 User/Assistant，不泄露 Tool 原始数据；
- Markdown 渲染通过 XSS 防护测试；
- 桌面端和移动端核心流程可用，键盘可完成主要操作；
- 单元、组件和端到端关键测试通过；
- CORS、取消、引用、鉴权 Token 等联调缺口均有明确处理结论；
- README 记录启动命令、环境变量、代理方式和联调步骤。

## 17. 第一批实际开发任务

第一批提交建议严格限制为可验证的纵向切片：

1. 创建 `frontend/` Next.js + TypeScript 工程；
2. 建立 `contracts.ts`、统一 API Client 和 `ApiError`；
3. 完成员工号登录、首次改密页及 `/api/auth/me` 登录态恢复；
4. 完成会话列表、新建会话和历史消息展示；
5. 编写独立 SSE Parser，并用随机 Chunk 单元测试覆盖；
6. 实现最小 `useChatStream`：处理 `run.started`、`text.delta`、`run.completed`、`run.failed`；
7. 实现 `StreamingMessage` 局部缓冲和 AbortController；
8. 与 FastAPI 联调一条“员工号登录 → 首次改密（如需要）→ 新建会话 → 流式提问 → 刷新恢复”的完整链路。

这一批完成后，再接入 Tool 状态、智能滚动、案件 Mention 和完整 Markdown，可以显著降低 UI 功能堆叠后才发现协议不兼容的返工风险。
