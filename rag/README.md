# 外部 RAG 查询工具接入

本目录的 app.py 是外部服务的接口参考，不是本项目内可单独启动的 RAG 实现。
外部服务仍在 law 工程、rag 环境中运行：

```powershell
python scripts/serve_api.py --host 127.0.0.1 --port 8001
```

## 已接入的工具

当前 Agent 注册两个互补的只读工具：

- **search_legal_kb**：按自然语言查询检索证据，结果按 Token 预算裁剪。
- **get_legal_source**：仅在检索结果带 `<RAG_KNOWLEDGE_TRUNCATED>` 标记时，按原样 `sourceId` 精确回查完整来源。

调用关系：Node 工具 → Python 中台 POST /internal/knowledge/search → 外部 RAG POST /retrieve。
全文回查关系：Node 工具 → Python 中台 POST /internal/knowledge/source → 外部 RAG POST /source。
Python 与 Node 间沿用 INTERNAL_SERVICE_TOKEN；该凭证不会转发给外部 RAG。
外部 RAG 当前没有鉴权，应仅限本机/受控私网访问。

- /health：检测 RAG 是否初始化完成。
- /retrieve：工具使用，返回检索证据，不执行 /ask 的最终答案生成步骤。
- /source：按 source_id 精确返回向量库中的完整原文，不执行 embedding 或模糊检索。
- /ask：未接入，避免重复生成答案。注意 /retrieve 内仍会调用意图解析器，接口源码不能保证内部完全没有模型调用。

工具参数示例：

```json
{
  "query": "盗窃罪，寻找类似案情及相关法条",
  "mode": "local",
  "limit": 5
}
```

mode 可选 hybrid（默认）、local、global、auto、graphrag。
query 由 Agent 生成，limit 映射为 top_k（上限 20）。
sourceTypes 可选 statute/case/knowledge，是对已返回候选集的本地过滤，不保证覆盖全库；通常建议不设置。
原接口没有 jurisdiction/effectiveAt 硬过滤，对这些参数明确返回不支持，避免虚假宣称已经过滤。

## 本机配置

在项目根目录 .env.local（由 start.cmd 的启动脚本读取）配置：

```dotenv
KNOWLEDGE_BACKEND=rag
RAG_BASE_URL=http://127.0.0.1:8001
RAG_MODE=hybrid
RAG_TIMEOUT_SECONDS=60
TOOL_TIMEOUT_MS=65000
RUN_TIMEOUT_MS=180000
```

Python 默认已选择 rag；一键启动脚本也会补齐未指定的本地默认值。
已有显式 mock 配置需手动改为 rag。修改配置后重启中台与 Agent；不必重建数据库或改动 RAG 索引。
Node 的 KNOWLEDGE_BASE_URL 应保持 http://127.0.0.1:8000（Python 中台），不要误设成 8001。
单独启动时通过进程环境设置上述变量，Python 不会自行读取 .env.example。
TOOL_TIMEOUT_MS 应大于 RAG_TIMEOUT_SECONDS×1000，RUN_TIMEOUT_MS 应留出模型推理时间。

若使用 Docker，中台的 RAG_BASE_URL 改成 http://host.docker.internal:8001。
绑定 127.0.0.1 的主机 RAG 不一定能被容器访问：若连通性测试失败，需在受防火墙保护的主机网卡上监听，
不要把无鉴权 RAG 直接公开到公网。纯本机运行不需要改变当前的 127.0.0.1 监听地址。

## 证据契约

- hit_id 原样作为 sourceId，不把检索命中 ID 伪装成法条编号。
- text 映射为 excerpt；原始 source_type 保存为 retrievalSourceType。
- 明确的 law/statute 映射为 statute；case/judgment 或 metadata.source=cail 的 chunk 映射为 case。
- 其余图谱摘要、关系、实体或来源不明片段标记为 knowledge，不当作现行法条。
- 只保留受限的来源元数据：doc_id、source、bucket、罪名、原始法条编号、刑期等；
  CAIL 样本中的 relevant_articles 仅是来源元数据，不代表已核验该法条的现行效力。
- Python 限制原始响应大小、结果数和文本长度；Node 继续按照 Token 预算瘦身。
- 检索超时、服务不可用或结构异常时输出错误，不退回模拟证据；空结果则正常返回空列表。

## 手动验证

先确认健康状态，再检索。健康通过只说明初始化完成，不保证每种检索模式都能及时完成。

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
$body = @{ query = '盗窃罪'; mode = 'local'; top_k = 2 } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8001/retrieve -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 60
```

在 Agent 聊天中输入“请调用知识库检索盗窃罪的类似案例，优先 local 模式”。
应看到 search_legal_kb 的 tool.started/tool.completed；最终 newMessages 中包含真实 sourceId 的 Tool Result。
实际问答质量还取决于 Node 模型配置，MOCK_MODE=true 仅用于模拟推理联调。

回归测试：

```powershell
# 在 mid-layer 目录中，使用装有开发依赖的 Python 环境
python -m pytest -q
# 在 agent-engine 目录中
npm test
npm run typecheck
```

## 本次验证（2026-08-30）

- 使用本机 law-agent Python 环境：18 项测试通过。
- Node：26 项测试通过，typecheck、lint、build 通过。
- 真实工具 search_legal_kb 经测试用中台调用 hybrid 检索“盗窃罪”：约 14.94 秒，
  返回 2 条 CAIL 案件片段，瘦身估算 878 Token，未遗漏候选条目。
- 单独 local/hybrid 查询也成功；首次“租赁合同欠付租金”hybrid 请求曾在 60 秒超时，
  因此不能保证全部查询和模式都在此时间内返回。服务的检索耗时问题需在 RAG 端进一步排查。
- 临时验证中台（18080 端口）已关闭；用户原有 RAG 服务未停止、业务数据库未写入。
