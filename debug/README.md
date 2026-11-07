# RAG 延迟诊断

`test_rag_latency.py` 用来区分以下问题：

- RAG 第一次检索是否存在模型或索引冷启动；
- RAG 预热后是否仍然持续缓慢；
- RAG 是否在第一次请求后退出；
- Python 中台是否产生明显额外耗时。

## 使用方法

先启动外部 RAG。为了测到真实冷启动，建议重启 RAG 后立即执行：

```powershell
python .\debug\test_rag_latency.py --rounds 5
```

脚本按两个阶段运行：

1. 连续 5 次直接请求 `http://127.0.0.1:8001/retrieve`；
2. 如果 Python 中台可用，再连续 5 次请求中台的知识库转发接口。

只测试 RAG：

```powershell
python .\debug\test_rag_latency.py --rounds 5 --skip-mid
```

使用其他查询：

```powershell
python .\debug\test_rag_latency.py `
  --query "交通肇事致一人死亡并承担全部责任的类似案例" `
  --rounds 5
```

结果会写入：

```text
debug/results/rag_diagnostic_时间.json
```

## 如何判断

- 首次耗时很高、后续明显变快：优先检查本地 Embedding 模型懒加载和 CUDA 初始化；
- 后续请求仍超过 5 秒：继续检查 JSON 向量扫描、数据库查询和检索实现；
- 第一次成功、随后失败或健康检查失败：检查 RAG 进程内存、CUDA OOM 和服务日志；
- 直连 RAG 快、中台路径慢：检查中台 HTTP 转发和结果规范化；
- 两条路径耗时接近：主要瓶颈位于 RAG，而不是中台或 Agent Engine。

脚本不会调用 Agent 或评分模型，也不会修改数据库和知识库。
