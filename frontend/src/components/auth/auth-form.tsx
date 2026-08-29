"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, LoaderCircle, LockKeyhole, Mail, Scale } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import * as authApi from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { setToken } from "@/lib/auth/token-store";

const schema = z.object({ email: z.string().email("请输入有效邮箱"), password: z.string().min(8, "密码至少 8 位") });

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const parsed = schema.safeParse({ email, password });
    if (!parsed.success) return setError(parsed.error.issues[0]?.message ?? "请检查输入");
    if (mode === "register" && password !== confirm) return setError("两次输入的密码不一致");
    setLoading(true);
    try {
      if (mode === "register") await authApi.register(email, password);
      const token = await authApi.login(email, password);
      setToken(token.access_token);
      await authApi.getMe();
      router.replace("/chat");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "暂时无法连接服务，请稍后重试");
    } finally { setLoading(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-aside">
        <div className="auth-brand"><span className="brand-mark"><Scale size={22} /></span><div><strong>衡法智策</strong><small>政企法律智能助手</small></div></div>
        <div className="auth-copy"><p className="eyebrow">LEGAL INTELLIGENCE PLATFORM</p><h1>让复杂法律问题<br />回归清晰判断</h1><p>连接案件事实、法律规范与企业决策，为每一次咨询提供可追溯的专业依据。</p></div>
        <div className="auth-quote">“明法于心，守法于行，智策于事。”</div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="mobile-auth-brand"><Scale size={22} /><strong>衡法智策</strong></div>
          <p className="eyebrow">{mode === "login" ? "WELCOME BACK" : "CREATE ACCOUNT"}</p>
          <h2>{mode === "login" ? "登录法律工作台" : "创建您的账户"}</h2>
          <p className="auth-hint">{mode === "login" ? "继续处理您的案件与法律咨询" : "开始管理案件与法律咨询"}</p>
          <label className="field"><span>工作邮箱</span><div><Mail size={17} /><input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" placeholder="name@company.com" required /></div></label>
          <label className="field"><span>密码</span><div><LockKeyhole size={17} /><input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder="至少 8 位" required /></div></label>
          {mode === "register" && <label className="field"><span>确认密码</span><div><LockKeyhole size={17} /><input value={confirm} onChange={(e) => setConfirm(e.target.value)} type="password" autoComplete="new-password" placeholder="再次输入密码" required /></div></label>}
          {error && <div className="form-error" role="alert">{error}</div>}
          <Button className="auth-submit" disabled={loading} type="submit">{loading ? <LoaderCircle className="spin" size={18} /> : <>{mode === "login" ? "进入工作台" : "注册并进入"}<ArrowRight size={17} /></>}</Button>
          <p className="auth-switch">{mode === "login" ? "还没有账户？" : "已经有账户？"}<Link href={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "立即注册" : "返回登录"}</Link></p>
        </form>
      </section>
    </main>
  );
}
