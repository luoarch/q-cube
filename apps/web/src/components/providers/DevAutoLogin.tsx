"use client";

import { use } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

const loginPromise: Promise<void> =
  typeof window === "undefined"
    ? Promise.resolve()
    : (async () => {
        const token = localStorage.getItem("q3_token");
        if (token) return;

        try {
          const r = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: "demo@q3.local", password: "demo12345" }),
          });
          const data = (await r.json()) as { accessToken?: string };
          if (data.accessToken) {
            localStorage.setItem("q3_token", data.accessToken);
          }
        } catch {
          // ignore login failure in dev
        }
      })();

export function DevAutoLogin({ children }: { children: React.ReactNode }) {
  use(loginPromise);
  return <>{children}</>;
}
