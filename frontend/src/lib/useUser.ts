"use client";
import { useEffect, useState } from "react";
import { api, API_BASE } from "./api";

export type User = {
  id: string;
  email: string;
  role: "customer" | "staff" | "admin";
};

const CACHE = "nimbus-user";

export function cacheUser(u: User | null) {
  try {
    if (u) localStorage.setItem(CACHE, JSON.stringify(u));
    else localStorage.removeItem(CACHE);
  } catch {}
}

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false); // the cache has been consulted
  useEffect(() => {
    // the last known sign-in renders the app instantly; /users/me reconciles in the
    // background once the free-tier backend wakes, instead of blocking the page on it
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE) || "null");
      if (cached) setUser(cached);
    } catch {}
    setReady(true);
    let dead = false;
    let timer: ReturnType<typeof setTimeout>;
    const check = () => {
      api("/users/me")
        .then((u) => {
          if (dead) return;
          setUser(u);
          cacheUser(u);
          setLoading(false);
        })
        .catch((e) => {
          if (dead) return;
          if (String(e instanceof Error ? e.message : e).startsWith("401")) {
            // a real "who are you": the session is genuinely gone
            setUser(null);
            cacheUser(null);
            setLoading(false);
          } else {
            // backend asleep or mid-deploy: that is not a sign-out, retry until it answers
            timer = setTimeout(check, 6000);
          }
        });
    };
    check();
    return () => {
      dead = true;
      clearTimeout(timer);
    };
  }, []);
  return { user, loading, ready };
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (res.ok) return;
  throw new Error("Wrong email or password");
}

export async function register(email: string, password: string) {
  await api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  // registering does not open a session, so the caller signs in straight after
}

export async function logout() {
  cacheUser(null);
  await api("/auth/logout", { method: "POST" });
}
