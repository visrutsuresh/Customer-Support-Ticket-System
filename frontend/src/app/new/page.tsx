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
        <form onSubmit={submit} className="card mt-4">
          <h1 className="text-[24px] font-bold mb-6">New request</h1>
          <label className="field">Subject</label>
          <input
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="input mb-6 text-[15px]"
          />
          <label className="field">What&apos;s going on?</label>
          <textarea
            required
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="input-box h-40 text-[14px] leading-relaxed"
          />
          {error && <p className="text-sm text-[var(--rust)] mt-3">{error}</p>}
          <div className="flex gap-4 items-center mt-5">
            <button
              type="submit"
              disabled={busy}
              className="btn"
            >
              {busy ? "Sending…" : "Send request"}
            </button>
            <button type="button" onClick={() => router.push("/")} className="btn-link btn-link-mut">
              Cancel
            </button>
          </div>
        </form>
      )}
    </PortalShell>
  );
}
