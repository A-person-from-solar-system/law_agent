"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, KeyRound, LoaderCircle, LockKeyhole, Scale, ShieldCheck } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { changePassword } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useRequireAuth } from "@/hooks/use-require-auth";

const strongPassword = z.string().min(12, "新密码至少 12 位").regex(/[A-Za-z]/, "新密码必须包含字母").regex(/\d/, "新密码必须包含数字");

export function ChangePasswordForm() {
  const ready = useRequireAuth({ allowPasswordChange: true });
  const router = useRouter(); const client = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError("");
    const checked = strongPassword.safeParse(newPassword);
    if (!checked.success) return setError(checked.error.issues[0]?.message ?? "请检查新密码");
    if (newPassword !== confirmPassword) return setError("两次输入的新密码不一致");
    if (currentPassword === newPassword) return setError("新密码不能与当前密码相同");
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      await client.invalidateQueries({ queryKey: ["me"] });
      router.replace("/chat");
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "修改密码失败，请稍后重试"); }
    finally { setLoading(false); }
  }

  if (!ready) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在验证员工身份</span></div>;
  return (
    <main className="auth-page">
      <section className="auth-aside password-aside">
        <div className="auth-brand"><span className="brand-mark"><Scale size={22} /></span><div><strong>法律知识问答智能体软件V1.0</strong><small>法律知识智能问答</small></div></div>
        <div className="auth-copy"><p className="eyebrow">ACCOUNT SECURITY</p><h1>首次登录<br />请设置新密码</h1><p>初始密码仅用于首次身份验证。更新密码后，才能进入案件与法律咨询工作台。</p></div>
        <div className="auth-quote"><ShieldCheck size={17} /> 密码不会以明文形式保存</div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <div className="mobile-auth-brand"><Scale size={22} /><strong>法律知识问答智能体软件V1.0</strong></div>
          <p className="eyebrow">SECURE YOUR ACCOUNT</p><h2>设置您的新密码</h2><p className="auth-hint">完成后将自动进入法律工作台</p>
          <label className="field"><span>当前临时密码</span><div><KeyRound size={17} /><input value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} type="password" autoComplete="current-password" placeholder="输入管理员提供的临时密码" required /></div></label>
          <label className="field"><span>新密码</span><div><LockKeyhole size={17} /><input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} type="password" autoComplete="new-password" placeholder="至少 12 位，包含字母和数字" required /></div></label>
          <label className="field"><span>确认新密码</span><div><LockKeyhole size={17} /><input value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} type="password" autoComplete="new-password" placeholder="再次输入新密码" required /></div></label>
          <div className="password-rules"><span className={newPassword.length >= 12 ? "rule-valid" : ""}><Check size={12} />至少 12 位</span><span className={/[A-Za-z]/.test(newPassword) ? "rule-valid" : ""}><Check size={12} />包含字母</span><span className={/\d/.test(newPassword) ? "rule-valid" : ""}><Check size={12} />包含数字</span></div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <Button className="auth-submit" disabled={loading} type="submit">{loading ? <LoaderCircle className="spin" size={18} /> : <>保存并进入工作台<ArrowRight size={17} /></>}</Button>
        </form>
      </section>
    </main>
  );
}
