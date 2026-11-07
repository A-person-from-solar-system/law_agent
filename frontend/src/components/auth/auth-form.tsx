"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BadgeCheck, IdCard, LoaderCircle, LockKeyhole, Scale } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import * as authApi from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { setToken } from "@/lib/auth/token-store";

const schema = z.object({
  employeeNo: z.string().regex(/^\d{6,10}$/, "员工号必须为 6 至 10 位数字"),
  password: z.string().min(1, "请输入密码"),
});

export function AuthForm() {
  const router = useRouter();
  const [employeeNo, setEmployeeNo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const parsed = schema.safeParse({ employeeNo, password });
    if (!parsed.success) return setError(parsed.error.issues[0]?.message ?? "请检查输入");
    setLoading(true);
    try {
      const token = await authApi.login(employeeNo, password);
      setToken(token.access_token);
      if (token.requires_password_change) router.replace("/change-password");
      else {
        await authApi.getMe();
        router.replace("/chat");
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "暂时无法连接服务，请稍后重试");
    } finally { setLoading(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-aside">
        <div className="auth-brand"><span className="brand-mark"><Scale size={22} /></span><div><strong>法律知识问答智能体软件V1.0</strong><small>法律知识智能问答</small></div></div>
        <div className="auth-copy"><p className="eyebrow">LEGAL INTELLIGENCE PLATFORM</p><h1>让复杂法律问题<br />回归清晰判断</h1><p>连接案件事实、法律规范与企业决策，为每一次咨询提供可追溯的专业依据。</p></div>
        <div className="auth-quote">“明法于心，守法于行，智策于事。”</div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="mobile-auth-brand"><Scale size={22} /><strong>法律知识问答智能体软件V1.0</strong></div>
          <p className="eyebrow">EMPLOYEE SIGN IN</p>
          <h2>登录法律工作台</h2>
          <p className="auth-hint">使用管理员为您开通的员工账号</p>
          <label className="field"><span>员工号</span><div><IdCard size={17} /><input value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" pattern="[0-9]{6,10}" autoComplete="username" placeholder="请输入 6～10 位员工号" required /></div></label>
          <label className="field"><span>密码</span><div><LockKeyhole size={17} /><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" placeholder="初始密码或当前密码" required /></div></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <Button className="auth-submit" disabled={loading} type="submit">{loading ? <LoaderCircle className="spin" size={18} /> : <>进入工作台<ArrowRight size={17} /></>}</Button>
          <div className="managed-account-note"><BadgeCheck size={15} /><span>账号由管理员统一开通。如忘记密码或账号被锁定，请联系系统管理员。</span></div>
        </form>
      </section>
    </main>
  );
}
