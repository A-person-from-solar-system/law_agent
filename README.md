# Law Agent 2.0

本仓库包含三个已串联服务：

- `frontend`：Next.js Web 客户端，统一从 `/backend` 代理访问中台；
- `mid-layer`：FastAPI 鉴权、会话、案件、PostgreSQL 持久化和 SSE 网关；
- `agent-engine`：无状态 Node.js Agent，并通过内部 API 回调 Python 法律知识库。

## 系统演示图

### 登录界面：

![image-20261107234811275](C:/Users/User/AppData/Roaming/Typora/typora-user-images/image-20261107234811275.png)

### 系统界面

![image-20261107235112762](C:/Users/User/AppData/Roaming/Typora/typora-user-images/image-20261107235112762.png)

## Windows 本机一键启动（不需要 Docker）

首次配置：把 `scripts/local.env.example` 复制为**项目根目录** `.env.local`，填写当前 PostgreSQL 连接；如后端不使用项目 `.venv`，设置 `LOCAL_PYTHON` 为正常运行中台的 Python 完整路径。

```powershell
Copy-Item scripts/local.env.example .env.local
# 编辑 .env.local 后，先检查环境
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local-stack.ps1 -Action Check
```

以后双击根目录 **start.cmd** 即可依次启动中台、计算引擎、前端，并打开三个实时日志窗口；双击 **stop.cmd** 停止本次启动器管理的三个进程树。访问 http://127.0.0.1:3000 。也可以在终端执行 `./start.cmd`、`./stop.cmd`。

- 日志在 `.local-run/*.out.log` 和 `*.err.log`，重启时覆盖；服务运行中可执行 `./logs.cmd`，或 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local-stack.ps1 -Action Logs` 重新打开三个日志窗口。每个窗口会同时跟随该服务的 `OUT` 和 `ERR`。
- 占用端口或依赖缺失时明确报错，不会强杀你手动启动的程序；启动失败会回收本次启动的进程。
- PostgreSQL 仍需提前运行；启动器只检查连接和业务表，不安装软件、不创建账号、不自动执行数据库迁移。
- Python 默认使用 `mid-layer/.venv/Scripts/python.exe`。依赖安装：进入 `mid-layer`，用选定的 Python 执行 `-m pip install -e ".[dev]"`。
- Node.js 需要 22+，两个 Node 项目均需先执行 `npm ci`。
- 模型配置继续读取 `agent-engine/.env`；启动器统一覆盖本机服务地址及内部令牌，使 Agent 通过 Python 知识接口检索。
- 根目录 `.env.local` 仅供本机启动器读取，与 `frontend/.env.local`、Docker 的根目录 `.env` 不同；不要提交私密配置和运行记录。

## Docker Compose 一键启动

1. 可选：复制根目录 `.env.example` 为 `.env` 并替换开发密钥；
2. 构建并启动全部服务：

```powershell
docker compose up --build -d
```

首次启动会自动执行 Alembic 数据库迁移。服务地址：

- 前端：http://localhost:3000
- Python API：http://localhost:8000/docs
- Agent 健康检查：http://localhost:3100/health

运行跨服务冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

测试会验证前端可访问，并实际执行 `Agent -> Python /internal/knowledge/search` 的 Tool Calling 链路。

## 创建首个管理员

```powershell
docker compose exec mid-layer python -m app.cli.create_admin --employee-no 000001 --name 系统管理员
```

命令会输出一次性初始密码。用该密码在前端登录并完成首次强制改密，然后即可创建员工、案件、会话并进行完整聊天。

## 切换真实模型

在根目录 `.env` 中配置：

```dotenv
MOCK_MODE=false
MODEL_PROVIDER=openai
MODEL_ID=<实际模型 ID>
MODEL_API_KEY=<密钥>
```

随后重新运行 `docker compose up --build -d`。正式环境还需把 `KNOWLEDGE_BACKEND=mock` 替换为真实只读知识库适配器，并使用随机强密钥。
