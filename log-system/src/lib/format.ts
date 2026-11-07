export const formatDateTime = (value?: string | null) => value ? new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(value)) : "—";
export const formatDuration = (value?: number | null) => value == null ? "—" : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(value < 10000 ? 2 : 1)} s`;
export const formatNumber = (value: number) => new Intl.NumberFormat("zh-CN").format(value);
export const statusLabel: Record<string, string> = { running: "运行中", completed: "已完成", failed: "失败", cancelled: "已取消", rejected: "已拒绝" };
