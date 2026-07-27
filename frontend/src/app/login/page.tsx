"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { login, register } from "@/lib/useUser";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [inboxWait, setInboxWait] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "signup") {
        await register(email, password);
        setInboxWait(true); // account exists; the verification link is on its way
        return;
      }
      await login(email, password);
      const me = await api("/users/me");
      router.push(me.role === "customer" ? "/" : "/workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (inboxWait) {
    return (
      <main className="min-h-[100dvh] bg-[var(--paper)] text-[var(--ink)] flex items-center justify-center px-4">
        <div className="w-full max-w-sm border-t-2 border-[var(--ink)] pt-8">
          <h1 className="text-2xl font-bold">Check your inbox</h1>
          <p className="text-sm text-[var(--mut)] mt-3 leading-relaxed">
            We sent a verification link to <b className="text-[var(--ink)]">{email}</b>. Open it to
            prove the inbox is yours, then sign in. Until then you can look around but not file
            requests.
          </p>
          <button
            onClick={() => {
              setInboxWait(false);
              setMode("signin");
            }}
            className="mt-6 text-sm text-[var(--ox)] underline underline-offset-4"
          >
            Back to sign in
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--paper)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm border-t-2 border-[var(--ink)] pt-8">
        <div className="mb-8">
          <div className="w-10 h-10 bg-[var(--ox)] text-[var(--paper)] flex items-center justify-center rounded-[3px] mb-3">
            <svg viewBox="0 0 24 18" width="26" height="20" fill="currentColor" aria-label="Nimbus cloud mark">
              <path d="M6.2 14.8c-2.1 0-3.6-1.4-3.6-3.2 0-1.5 1-2.7 2.4-3.1-.1-2.2 1.6-4 3.8-4 1.4 0 2.6.7 3.3 1.8.6-1.6 2.1-2.7 3.9-2.7 2.3 0 4.2 1.8 4.2 4.1 0 .3 0 .6-.1.9 1.2.5 2 1.6 2 3 0 1.8-1.5 3.2-3.4 3.2z" />
              <circle cx="12.6" cy="10.6" r="2.5" fill="var(--ox)" />
              <path d="M12.6 8.1a2.5 2.5 0 0 1 2.5 2.5" stroke="currentColor" strokeWidth="1.1" fill="none" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold">{mode === "signin" ? "Sign in" : "Create your account"}</h1>
          <p className="text-sm text-[var(--mut)] mt-1">
            {mode === "signin" ? "Nimbus support desk" : "Track your requests in one place"}
          </p>
        </div>

        <label className="block text-[11px] tracking-widest uppercase text-[var(--mut)] mb-1">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 mb-5"
        />
        <label className="block text-[11px] tracking-widest uppercase text-[var(--mut)] mb-1">Password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 mb-6"
        />

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy}
            className="bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-sm px-6 py-2.5 rounded-[3px] active:scale-[0.98] transition disabled:opacity-50"
          >
            {busy ? "One moment" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
            className="text-sm text-[var(--ox)] underline underline-offset-4"
          >
            {mode === "signin" ? "New here? Create an account" : "Have an account? Sign in"}
          </button>
        </div>
      </form>
    </main>
  );
}
