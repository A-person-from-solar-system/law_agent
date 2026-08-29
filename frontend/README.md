# 衡法智策前端

政企法律 Agent 的 Next.js Web 客户端，实现鉴权、会话历史、POST SSE 流式对话、Tool 状态、`@案件` 引用和案件库管理。

## 技术栈

- Next.js 16、React 19、TypeScript、App Router
- Tailwind CSS 4 与 shadcn 风格 Radix UI 基础组件
- TanStack Query
- react-markdown + remark-gfm
- Vitest、Testing Library、Playwright

## 本地启动

1. 复制 `.env.example` 为 `.env.local`；
2. 确认 FastAPI `mid-layer` 运行于 `http://localhost:8000`；
3. 安装依赖并启动：

```bash
npm install
npm run dev
```

访问 `http://localhost:3000`。默认通过 Next.js `/backend/*` 同源代理访问 FastAPI，因此本地开发不依赖浏览器 CORS 放行。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_API_URL` | `http://localhost:8000` | Next.js 服务端代理目标 |
| `NEXT_PUBLIC_API_BASE_URL` | `/backend` | 浏览器 API 前缀；同源部署建议保持默认值 |

## 验证命令

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

端到端测试首次运行前可能需要执行 `npx playwright install chromium`。

## 目录

```text
src/
  app/          路由、全局主题和 Providers
  components/   鉴权、聊天、案件、法律 Markdown、UI 基础组件
  hooks/        登录保护与流式对话状态
  lib/api/      FastAPI 契约和请求层
  lib/sse/      增量 SSE 解析器
  tests/        测试初始化与端到端用例
```

## 安全说明

当前后端只提供 Access Token，前端按现有契约暂存于 `localStorage`。生产环境应由后端升级为 HttpOnly Cookie 或短期 Access Token + Refresh Token，并同步调整前端登录态逻辑。
