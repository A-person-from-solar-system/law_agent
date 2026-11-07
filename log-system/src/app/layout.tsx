import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "运行审计 · 法律 Agent",
  description: "法律 Agent 管理员日志与调用监控系统",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
