# 法律 Agent 日志管理系统

独立管理员前端，复用 Python 中台的员工账号与 JWT。默认运行于 `http://localhost:3200`，避免与业务前端的 3000 端口和 Agent Engine 的 3100 端口冲突。

## 启动

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

当前示例配置默认连接真实中台。仅需独立预览界面时，才把 `.env.local` 中的 `NEXT_PUBLIC_DEMO_MODE` 改为 `true`；演示数据仅存在浏览器内。

## 中台接口

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/admin/agent-runs`
- `GET /api/admin/agent-runs/{runId}`
- `GET /api/admin/agent-runs/{runId}/events`
- `GET /api/admin/agent-runs/{runId}/tool-calls`
- `GET /api/admin/agent-metrics/summary`

生产环境不得启用演示模式。日志前端只连接 Python 中台，不直接访问数据库、Agent Engine 或 RAG。
