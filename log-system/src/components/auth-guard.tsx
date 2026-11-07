"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import type { User } from "@/lib/contracts";

export function AuthGuard({ children }: { children: (user: User) => React.ReactNode }) {
  const router = useRouter(); const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null); const [error, setError] = useState("");
  useEffect(() => {
    if (!getToken()) { router.replace(`/login?next=${encodeURIComponent(pathname)}`); return; }
    getMe().then((item) => { if (item.role !== "admin") { clearToken(); setError("当前账号不是管理员，无法访问运行审计系统。此限制同时由中台强制执行。"); return; } setUser(item); }).catch(() => router.replace("/login"));
  }, [pathname, router]);
  if (error) return <main className="center-state"><div className="state-card"><span className="kicker">ACCESS DENIED</span><h1>权限不足</h1><p>{error}</p><button onClick={() => router.replace("/login")}>返回登录</button></div></main>;
  if (!user) return <main className="center-state"><div className="loader" /><span>正在验证管理员权限…</span></main>;
  return children(user);
}
