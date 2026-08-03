"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CloudMark, EyeIcon } from "@/lib/icons";
import { login, register } from "@/lib/useUser";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [showPw, setShowPw] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      // signing up creates the account but opens no session, so sign in straight after
      if (mode === "signup") await register(email, password);
      await login(email, password);
      const me = await api("/users/me");
      router.push(me.role === "customer" ? "/" : "/workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--paper)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm">
        <div className="mb-8">
          <CloudMark size={46} className="text-[var(--ox)] mb-3" />
          <h1 className="text-2xl font-bold">{mode === "signin" ? "Sign in" : "Create your account"}</h1>
          <p className="text-sm text-[var(--mut)] mt-1">
            {mode === "signin" ? "Nimbus support desk" : "Track your requests in one place"}
          </p>
        </div>

        <label className="field">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="input mb-5"
        />
        <label className="field">Password</label>
        <div className="relative mb-6">
          <input
            type={showPw ? "text" : "password"}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input w-full pr-9"
          />
          <button
            type="button"
            aria-label={showPw ? "Hide password" : "Show password"}
            onClick={() => setShowPw(!showPw)}
            className="absolute right-1 top-1/2 -translate-y-1/2 text-[var(--mut)] hover:text-[var(--ink)]"
          >
            <EyeIcon off={showPw} />
          </button>
        </div>

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy}
            className="btn"
          >
            {busy ? "One moment" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
            className="btn-link"
          >
            {mode === "signin" ? "New here? Create an account" : "Have an account? Sign in"}
          </button>
        </div>
      </form>
    </main>
  );
}
