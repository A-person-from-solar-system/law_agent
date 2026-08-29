"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth/token-store";

export function useRequireAuth() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const check = () => {
      if (!getToken()) { setReady(false); router.replace("/login"); }
      else setReady(true);
    };
    check();
    window.addEventListener("law-agent:unauthorized", check);
    return () => window.removeEventListener("law-agent:unauthorized", check);
  }, [router]);
  return ready;
}
