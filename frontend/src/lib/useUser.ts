"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type User = {
  id: string;
  email: string;
  role: "customer" | "staff" | "admin";
};

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api("/users/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  return { user, loading };
}

export class NotVerifiedError extends Error {}

export async function login(email: string, password: string) {
  const res = await fetch("http://localhost:8000/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (res.ok) return;
  // a proved inbox is a separate refusal from a wrong password; telling them apart is the point
  const body = await res.text();
  if (body.includes("LOGIN_USER_NOT_VERIFIED")) {
    throw new NotVerifiedError("Verify your email before signing in");
  }
  throw new Error("Wrong email or password");
}

export async function register(email: string, password: string) {
  await api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  // no auto sign-in: an account cannot hold a session until the inbox is proved
}

export async function resendVerification(email: string) {
  // always answers 202, whether or not the address exists: no account fishing
  await fetch("http://localhost:8000/auth/request-verify-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function logout() {
  await api("/auth/logout", { method: "POST" });
}
