"use client";

import { useEffect, useState } from "react";
import { Activity, CircleCheckBig, Clock3, Cpu, DatabaseZap, TriangleAlert, Wrench } from "lucide-react";
import { getMetrics } from "@/lib/api";
import type { MetricsSummary } from "@/lib/contracts";
import { formatDuration, formatNumber } from "@/lib/format";
import { AuthGuard } from "./auth-guard";
import { AppShell } from "./app-shell";

export function MetricsView() { return <AuthGuard>{(user) => <AppShell user={user}><Metrics /></AppShell>}</AuthGuard>; }
function Metrics() {
  const [data, setData] = useState<MetricsSummary | null>(null); const [error, setError] = useState("");
  useEffect(() => { let active = true; getMetrics().then((value) => { if (active) setData(value); }).catch(() => { if (active) setError("指标加载失败，请检查中台服务、数据库迁移和管理员权限。"); }); return () => { active = false; }; }, []);
  if (error) return <div className="empty-state full error">{error}</div>;
  if (!data) return <div className="empty-state full"><div className="loader" />正在汇总运行指标…</div>;
  const max = Math.max(1, ...data.trend.map((item) => item.completed + item.failed));
  return <><header className="topbar"><div><span className="kicker">SYSTEM METRICS</span><h1>指标概览</h1><p>观察运行健康度、延迟、Token 用量与错误分布</p></div><span className="range-chip"><Activity />最近 24 小时</span></header><section className="page-content"><div className="metric-grid"><MetricCard icon={<DatabaseZap />} label="总运行数" value={formatNumber(data.total_runs)} note={`${data.active_runs} 个正在运行`} /><MetricCard icon={<CircleCheckBig />} label="成功率" value={`${data.success_rate.toFixed(1)}%`} note={`${data.failed_runs} 次非成功终态`} good /><MetricCard icon={<Clock3 />} label={data.avg_duration_ms != null ? "平均总耗时" : "P95 总耗时"} value={formatDuration(data.avg_duration_ms ?? data.p95_duration_ms)} note={`平均首字 ${formatDuration(data.avg_first_token_ms)}`} /><MetricCard icon={<Cpu />} label="Token 总量" value={formatNumber(data.input_tokens + data.output_tokens)} note={`输出 ${formatNumber(data.output_tokens)}`} /><MetricCard icon={<Wrench />} label={data.tool_success_rate == null ? "工具调用" : "工具成功率"} value={data.tool_success_rate == null ? formatNumber(data.tool_call_count ?? 0) : `${data.tool_success_rate}%`} note="法律知识检索工具" good /></div><div className="dashboard-grid"><section className="panel chart-panel"><div className="panel-title"><div><span className="icon-box"><Activity /></span><div><h2>运行趋势</h2><p>中台提供按日聚合后将在此展示</p></div></div><div className="legend"><span><i className="completed" />已完成</span><span><i className="failed" />失败</span></div></div>{data.trend.length ? <div className="bar-chart">{data.trend.map((item) => <div className="bar-column" key={item.label}><div className="bar-track"><i className="bar-failed" style={{ height: `${item.failed / max * 100}%` }} /><i className="bar-completed" style={{ height: `${item.completed / max * 100}%` }} /></div><span>{item.label}</span></div>)}</div> : <div className="empty-state">当前中台接口暂未提供按日趋势数据</div>}</section><section className="panel error-ranking"><div className="panel-title"><div><span className="icon-box danger-box"><TriangleAlert /></span><div><h2>错误分布</h2><p>按标准错误码统计</p></div></div></div>{data.errors.length ? data.errors.map((item, i) => <div className="error-rank" key={item.code}><span>{i + 1}</span><div><strong>{item.code}</strong><i><b style={{ width: `${item.count / data.errors[0].count * 100}%` }} /></i></div><em>{item.count}</em></div>) : <div className="empty-inline">当前时间范围内没有错误</div>}</section></div></section></>;
}
function MetricCard({ icon, label, value, note, good = false }: { icon: React.ReactNode; label: string; value: string; note: string; good?: boolean }) { return <article className="big-metric"><span className={good ? "good" : ""}>{icon}</span><p>{label}</p><strong>{value}</strong><small>{note}</small></article>; }
