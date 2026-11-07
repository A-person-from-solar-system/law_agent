import { Suspense } from "react";
import { LoginView } from "@/components/login-view";

export default function LoginPage() {
  return <Suspense fallback={<main className="center-state"><div className="loader" /><span>正在加载登录页面…</span></main>}><LoginView /></Suspense>;
}
