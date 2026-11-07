# Agent 离线评测程序

## 使用方式

推荐在项目根目录执行：

```powershell
python -m eval_agent.code.main --limit 1
```

如果当前已经进入 `eval_agent/code`，也可以直接执行：

```powershell
python main.py --limit 1
```

### 1. 只校验数据集

```powershell
python -m eval_agent.code.main --dry-run
```

### 2. 先运行一条任务

确保 Agent Engine 和 RAG 链路已启动，然后执行：

```powershell
python -m eval_agent.code.main --limit 1
```

### 3. 运行指定数据集

```powershell
python -m eval_agent.code.main --datasets tool_call_eval.jsonl
```

### 4. 运行全部数据集

```powershell
python -m eval_agent.code.main
```

## 配置

程序会先读取 `agent-engine/.env`，再读取 `eval_agent/code/.env`；已经存在的环境变量不会被覆盖。可以复制 `.env.example` 为 `.env` 并填写评测专用配置。

默认情况下，程序直接复用 `agent-engine/.env` 中的 `MODEL_PROVIDER`、`MODEL_ID` 和 `MODEL_API_KEY` 作为评分模型配置。当前项目使用 DeepSeek 时，会使用 `https://api.deepseek.com/chat/completions`。如需改用独立评分模型，再通过 `EVAL_JUDGE_*` 覆盖。

如果项目模型和 `EVAL_JUDGE_*` 都未配置：

- 事实识别、来源可追溯性、工具调用判断和多案件事实提取正常评分；
- 处置建议标记为“未评分”；
- Agent 原始运行结果仍会正常保存。

评分模型接口需要兼容 `POST /chat/completions`。

## 输出

```text
eval_agent/runs/{run_id}/run_config.json
eval_agent/runs/{run_id}/results.jsonl
eval_agent/reports/{run_id}/scores.json
eval_agent/reports/{run_id}/summary.md
```

基础数据集不会被写入或修改。

## 单案件事实识别评分

基础案件任务仍要求 Agent 正常完成法律分析和处置建议，但会在提示词中额外要求其在回答末尾输出 `FACTS_JSON`。其中固定包含 `person`、`time`、`location`、`behavior`、`numbers`、`responsibility` 和 `consequence` 七类事实。

评分器只解析该结构化事实块，与数据集中的人工 `fact_points` 逐项做规则匹配，并自动计算 TP、FP、FN、精确率、召回率和 F1，不再让评分模型直接决定这些计数。未返回合法事实块时，本项按 0 分处理；这不会影响来源可追溯性和处置建议继续读取回答正文。

## 处置建议评分

评测器会从内部 `run.completed.newMessages` 中提取并去重 Agent 本轮实际使用的 RAG evidence，再写入本地评测产物并作为 Judge 输入；该改动不会扩大原有 `tool.completed` 事件的字段范围。

处置建议使用 5 个固定检查项：罪名与处置方向、类案证据使用、关键处置因素、建议可用性、不确定性与结论一致性。历史案件的精确刑期和罚金保留在报告的 `observed_outcome` 中，但不会传给 Judge，也不属于主评分必答项。固定项加权得分不低于 75% 且无严重错误时，该 Task 通过。

## 多案件事实提取评分

多案件任务会自动改写为结构化事实提取请求，Agent 仅输出目标案件的 `caseId` 及人物、时间、地点、行为、关键数值、责任和案件后果。评分器直接与人工 `case_fact_map` 逐项比较，计算精确率、召回率、F1、跨案件错误率和非目标事实泄漏率，不调用评分模型。F1 不低于 80%、无案件错配且无范围泄漏时，该 Task 通过。
