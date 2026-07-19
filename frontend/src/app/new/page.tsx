"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import PortalShell from "../portal-shell";

export default function NewRequest() {
  const router = useRouter();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/tickets", { method: "POST", body: JSON.stringify({ subject, body, source: "form" }) });
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  }

  return (
    <PortalShell>
      {() => (
        <form onSubmit={submit} className="border-t-2 border-[var(--ink)] pt-6 mt-4">
          <h1 className="text-[24px] font-bold mb-6">New request</h1>
          <label className="block font-array text-[10.5px] text-[var(--mut)] mb-1">SUBJECT</label>
          <input
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 mb-6 text-[15px]"
          />
          <label className="block font-array text-[10.5px] text-[var(--mut)] mb-1">WHAT&apos;S GOING ON?</label>
          <textarea
            required
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full bg-white border border-[var(--line)] focus:border-[var(--ox)] outline-none rounded-[3px] p-3 h-40 text-[14px] leading-relaxed"
          />
          {error && <p className="text-sm text-[var(--rust)] mt-3">{error}</p>}
          <div className="flex gap-4 items-center mt-5">
            <button
              type="submit"
              disabled={busy}
              className="bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-[13.5px] px-6 py-2.5 rounded-[3px] active:scale-[0.98] transition disabled:opacity-50"
            >
              {busy ? "Sending…" : "Send request"}
            </button>
            <button type="button" onClick={() => router.push("/")} className="text-[13.5px] text-[var(--mut)] underline underline-offset-4">
              Cancel
            </button>
          </div>
        </form>
      )}
    </PortalShell>
  );
}
