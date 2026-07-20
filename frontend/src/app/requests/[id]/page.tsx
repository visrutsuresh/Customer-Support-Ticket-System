"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import PortalShell from "../../portal-shell";

type Msg = { role: string; body: string };

export default function RequestThread() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [msgs, setMsgs] = useState<Msg[] | null>(null);
  const [subject, setSubject] = useState("");
  const [resolved, setResolved] = useState(false);
  const [reply, setReply] = useState("");
  const [rating, setRating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api(`/tickets/${id}/thread`)
      .then((t) => setMsgs(t.messages))
      .catch((e) => {
        // a T- id dies when staff resolve it; the my/tickets branch below redirects to the HIST- twin
        if (!id.startsWith("T-")) setError(String(e));
      });
    api("/my/tickets")
      .then((list: { ticket_id: string; subject: string; lifecycle: string }[]) => {
        const mine =
          list.find((r) => r.ticket_id === id) ??
          (id.startsWith("T-") ? list.find((r) => r.ticket_id === `HIST-${id.slice(2)}`) : undefined);
        if (mine && mine.ticket_id !== id) {
          router.replace(`/requests/${mine.ticket_id}`);
          return;
        }
        if (mine) {
          setSubject(mine.subject);
          setResolved(mine.lifecycle === "resolved");
        }
      })
      .catch(() => {});
  }, [id, router]);

  useEffect(() => {
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, [load]);

  async function sendReply() {
    if (!reply.trim()) return;
    await api(`/tickets/${id}/reply`, { method: "POST", body: JSON.stringify({ body: reply }) });
    setReply("");
    load();
  }

  async function resolve(csat: number) {
    try {
      await api(`/tickets/${id}/resolve`, { method: "POST", body: JSON.stringify({ csat }) });
    } catch {
      // id can die mid-flight (T- renamed to HIST- by a racing resolve); home shows the truth either way
    }
    router.push("/");
  }

  if (error) return <PortalShell>{() => <p className="text-[var(--rust)]">{error}</p>}</PortalShell>;

  return (
    <PortalShell>
      {() => (
        <>
          <Link href="/" className="font-array text-[11px] text-[var(--mut)] hover:text-[var(--ox)]">
            ← YOUR REQUESTS
          </Link>
          <h1 className="text-[24px] font-bold mt-2 mb-6 border-b border-[var(--ink)] pb-4">{subject || "Your request"}</h1>
          {!msgs ? (
            <p className="text-[var(--mut)]">Loading…</p>
          ) : (
            <div className="space-y-6">
              {msgs.map((m, i) => (
                <div key={i} className="rise" style={{ "--i": i } as React.CSSProperties}>
                  <div className="font-array text-[10.5px] text-[var(--mut)] mb-1.5">
                    {m.role === "customer" ? "YOU" : "SUPPORT"}
                  </div>
                  <p
                    className={`whitespace-pre-wrap text-[14.5px] max-w-[58ch] pl-3.5 border-l-2 ${
                      m.role === "customer" ? "border-[var(--ink)]" : "border-[var(--ox)]"
                    }`}
                  >
                    {m.body}
                  </p>
                </div>
              ))}
            </div>
          )}

          {!resolved && !rating && (
            <div className="mt-10 flex gap-2">
              <input
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendReply()}
                placeholder="Write a reply"
                className="flex-1 bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 text-[14px]"
              />
              <button
                onClick={sendReply}
                className="bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-[13px] px-5 py-2 rounded-[3px] active:scale-[0.98] transition"
              >
                Send
              </button>
              <button
                onClick={() => setRating(true)}
                className="text-[var(--olive)] border border-[var(--olive)] font-semibold text-[13px] px-4 py-2 rounded-[3px] hover:bg-[var(--olive)] hover:text-[var(--paper)] transition-colors"
              >
                Resolve
              </button>
            </div>
          )}

          {rating && (
            <div className="mt-10">
              <p className="text-[14px] mb-3">How did we do? 1 is poor, 10 is excellent.</p>
              <div className="flex gap-1.5 flex-wrap">
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    onClick={() => resolve(n)}
                    className="w-9 h-9 font-array text-[13px] border border-[var(--line)] rounded-[3px] hover:bg-[var(--ox)] hover:text-[var(--paper)] hover:border-[var(--ox)] transition-colors"
                  >
                    {n}
                  </button>
                ))}
              </div>
              <button onClick={() => setRating(false)} className="mt-3 text-[12.5px] text-[var(--mut)] underline underline-offset-4">
                Never mind, keep it open
              </button>
            </div>
          )}

          {resolved && <p className="mt-10 font-array text-[11px] text-[var(--olive)]">RESOLVED · THANKS FOR WRITING IN</p>}
        </>
      )}
    </PortalShell>
  );
}
