"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

export function DevAutoLogin({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("q3_token");
    if (token) {
      setReady(true);
      return;
    }

    // Auto-login with demo credentials in development
    fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "demo@q3.local", password: "demo12345" }),
    })
      .then((r) => r.json())
      .then((data: { accessToken?: string }) => {
        if (data.accessToken) {
          localStorage.setItem("q3_token", data.accessToken);
        }
      })
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
