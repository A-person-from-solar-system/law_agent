# 政企法律智能咨询 Agent 系统

**2026.08 - 2026.08 ｜ 核心成员 / Agent 与后端方向 ｜ Next.js + FastAPI + Node.js + PostgreSQL + RAG + DeepSeek**

- **背景：** 项目面向政企内部法律咨询场景，解决通用大模型在多案件对话中容易上下文混淆、法律依据不可追溯、长会话成本高、权限隔离不足等问题，构建支持案件事实分析、法条/类案检索和流式问答的法律 Agent 系统。

- **数据与效果：** 作为核心成员参与前端、中台、Agent Engine **3 个核心服务**建设；负责/参与登录、员工管理、案件库、会话、聊天、内部 RAG、健康检查等 **20+ 个 REST/SSE 接口**联调；支持 **8 类流式事件**展示生成过程与工具状态；参与沉淀 **50+ 条单元/集成测试用例**，覆盖鉴权、SSE 解析、RAG 工具、上下文预算、消息回放和错误处理等核心链路。

- **Agent 架构：** 参与设计并负责落地基于 `pi-agent-core` 的请求级无状态 Agent，每轮动态注入系统提示词、历史消息、checkpoint 摘要、案件事实和工具 schema；协同采用“Python 中台管理状态 + Node.js Agent 按请求计算”的方式，避免常驻 Agent 带来的多用户串话和内存状态污染。

- **RAG 检索链路：** 负责 Agent 侧 `search_legal_kb` 白名单工具与 Python 中台知识接口对接，经中台调用外部 RAG `/retrieve` 接口；参与制定 evidence 结构，将检索结果统一规范为 `sourceId / sourceType / excerpt / metadata`，单次最多接收 **20 条候选证据**、默认保留 **5 条高相关证据**，支持回答依据追踪与后续复盘。

- **上下文工程：** 负责 Agent 侧 token budget 管理，并参与 checkpoint 压缩链路联调，统一计算系统提示词、工具 schema、历史消息、案件材料、RAG 证据、当前问题、输出预留和安全余量；针对 DeepSeek V4 Flash 支持 **256K 开发上下文配置**，并预留 **1M 上下文 profile**，避免长案情直接触发上下文溢出。

- **业务与安全：** 参与 FastAPI + PostgreSQL 业务中台开发，支持员工号登录、首次强制改密、管理员开通用户、重置密码、启用/禁用账号、案件归属校验和会话隔离；在 Agent 工具层限制数据库和任意 URL 访问，仅允许通过只读工具检索知识库，降低数据越权和误操作风险。

- **工程落地：** 负责 Agent 到前端的 SSE 流式链路联调，实现 `run.started / text.delta / tool.started / tool.completed / usage / run.completed / run.failed / checkpoint.pending` 等事件展示；参与完善 RAG 超时、模型超时、上下文超限、Agent 连接失败等错误分类，并补充一键启动脚本统一拉起 **3 个服务 + 3 个实时日志窗口**，提升本地联调和演示效率。
