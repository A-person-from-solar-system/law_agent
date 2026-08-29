"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth/token-store";
import { getMe } from "@/lib/api/auth";

export function useRequireAuth(options: { allowPasswordChange?: boolean } = {}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    const check = async () => {
      if (!getToken()) { setReady(false); router.replace("/login"); }
      else {
        try {
          const user = await getMe();
          if (!active) return;
          if (user.must_change_password && !options.allowPasswordChange) router.replace("/change-password");
          else if (!user.must_change_password && options.allowPasswordChange) router.replace("/chat");
          else setReady(true);
        } catch { if (active) setReady(false); }
      }
    };
    void check();
    const unauthorized = () => void check();
    const passwordChangeRequired = () => router.replace("/change-password");
    window.addEventListener("law-agent:unauthorized", unauthorized);
    window.addEventListener("law-agent:password-change-required", passwordChangeRequired);
    return () => {
      active = false;
      window.removeEventListener("law-agent:unauthorized", unauthorized);
      window.removeEventListener("law-agent:password-change-required", passwordChangeRequired);
    };
  }, [options.allowPasswordChange, router]);
  return ready;
}
