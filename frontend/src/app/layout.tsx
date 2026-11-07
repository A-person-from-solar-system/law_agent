import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: "法律知识问答智能体软件V1.0",
  description: "面向政企法律事务的案件分析、法条检索与智能咨询工作台",
  openGraph: {
    title: "法律知识问答智能体软件V1.0",
    description: "连接案件事实、法律规范与企业决策的智能法律工作台",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "法律知识问答智能体软件V1.0" }],
  },
  twitter: { card: "summary_large_image", title: "法律知识问答智能体软件V1.0", description: "法律知识智能问答", images: ["/og.png"] },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="zh-CN"><body><Providers>{children}</Providers></body></html>;
}
