"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { AdminUserInput } from "@/lib/api/contracts";

export function UserFormDialog({ open, busy, onOpenChange, onSubmit }: { open: boolean; busy: boolean; onOpenChange: (open: boolean) => void; onSubmit: (input: AdminUserInput) => Promise<void> }) {
  const [employeeNo, setEmployeeNo] = useState(""); const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [role, setRole] = useState<"employee" | "admin">("employee"); const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError("");
    if (!/^\d{6,10}$/.test(employeeNo)) return setError("员工号必须为 6 至 10 位数字");
    if (!name.trim()) return setError("请输入姓名");
    await onSubmit({ employee_no: employeeNo, name: name.trim(), email: email.trim() || null, role });
  }
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogTitle>添加用户</DialogTitle><DialogDescription>系统会生成一次性初始密码，新用户首次登录后需要修改密码。</DialogDescription><form className="case-form" onSubmit={submit}><label className="field"><span>员工号 *</span><div><input value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} maxLength={10} placeholder="例如：100001" /></div></label><label className="field"><span>姓名 *</span><div><input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} placeholder="例如：张三" /></div></label><label className="field"><span>邮箱</span><div><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="可选" /></div></label><label className="field"><span>角色</span><div><select value={role} onChange={(event) => setRole(event.target.value as "employee" | "admin")}><option value="employee">员工</option><option value="admin">管理员</option></select></div></label>{error && <div className="form-error" role="alert">{error}</div>}<div className="dialog-actions"><Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>取消</Button><Button disabled={busy} type="submit">{busy && <LoaderCircle className="spin" size={16} />}创建用户</Button></div></form></DialogContent></Dialog>;
}
