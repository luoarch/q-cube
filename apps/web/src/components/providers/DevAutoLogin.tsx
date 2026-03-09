"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

export function DevAutoLogin({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function ensureToken() {
      const existing = localStorage.getItem("q3_token");

      // Validate existing token
      if (existing) {
        try {
          const r = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${existing}` },
          });
          if (r.ok) {
            setReady(true);
            return;
          }
        } catch {
          // token invalid, will re-login below
        }
        localStorage.removeItem("q3_token");
      }

      // Login fresh
      try {
        const r = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: "demo@q3.dev", password: "Q3demo!2026" }),
        });
        const data = (await r.json()) as { accessToken?: string };
        if (data.accessToken) {
          localStorage.setItem("q3_token", data.accessToken);
        }
      } catch {
        // ignore login failure in dev
      } finally {
        setReady(true);
      }
    }

    ensureToken();
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
