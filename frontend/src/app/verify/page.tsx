"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"working" | "done" | "failed">("working");

  useEffect(() => {
    if (!token) {
      setState("failed");
      return;
    }
    api("/auth/verify", { method: "POST", body: JSON.stringify({ token }) })
      .then(() => setState("done"))
      .catch(() => setState("failed"));
  }, [token]);

  return (
    <main className="min-h-[100dvh] bg-[var(--paper)] text-[var(--ink)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm border-t-2 border-[var(--ink)] pt-8">
        {state === "working" && <p className="text-[var(--mut)]">Verifying your email…</p>}
        {state === "done" && (
          <>
            <h1 className="text-2xl font-bold">Email verified</h1>
            <p className="text-sm text-[var(--mut)] mt-3">
              Your account is ready. Sign in to file and track your requests.
            </p>
            <Link
              href="/login"
              className="inline-block mt-6 bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-sm px-6 py-2.5 rounded-[3px] transition"
            >
              Sign in
            </Link>
          </>
        )}
        {state === "failed" && (
          <>
            <h1 className="text-2xl font-bold">That link did not work</h1>
            <p className="text-sm text-[var(--mut)] mt-3">
              The link may have expired or was already used. Sign in and we can send a fresh one, or
              create the account again.
            </p>
            <Link href="/login" className="inline-block mt-6 text-sm text-[var(--ox)] underline underline-offset-4">
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </main>
  );
}

export default function VerifyPage() {
  // useSearchParams needs a Suspense boundary during prerender
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
