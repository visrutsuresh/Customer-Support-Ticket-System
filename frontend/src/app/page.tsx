"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import PortalShell from "./portal-shell";

type Req = { ticket_id: string; subject: string; human_status: string; lifecycle: string; created_at: string };

function statusPill(r: Req): { text: string; cls: string } {
  if (r.lifecycle === "resolved") return { text: "SOLVED", cls: "border border-[var(--line)] text-[var(--mut)]" };
  if (r.lifecycle === "awaiting_customer") return { text: "YOUR TURN", cls: "bg-[var(--ox)] text-[var(--paper)]" };
  if (r.human_status === "processing") return { text: "READING…", cls: "bg-[var(--paper-2)] text-[var(--olive)] border border-[var(--line)]" };
  return { text: "WE'RE ON IT", cls: "bg-[var(--paper-2)] text-[var(--olive)] border border-[var(--line)]" };
}

const QUICK = [
  { label: "A charge looks wrong", topic: "Billing" },
  { label: "Where's my order", topic: "An order" },
  { label: "Can't sign in", topic: "My account" },
];

export default function PortalHome() {
  const router = useRouter();
  const [reqs, setReqs] = useState<Req[] | null>(null);
  const [line, setLine] = useState("");

  useEffect(() => {
    const load = () => api("/my/tickets").then(setReqs).catch(() => setReqs([]));
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  function start() {
    router.push(line.trim() ? `/new?q=${encodeURIComponent(line.trim())}` : "/new");
  }

  const open = reqs?.filter((r) => r.lifecycle !== "resolved").length ?? 0;
  const solved = reqs?.filter((r) => r.lifecycle === "resolved").length ?? 0;

  return (
    <PortalShell>
      {(user) => (
        <>
          {/* the writing line: typing here IS starting the conversation */}
          <p
            className="font-array text-[13px] tracking-[0.15em] uppercase text-[var(--mut)] font-semibold mt-12 mb-3 rise"
            style={{ "--i": 0 } as React.CSSProperties}
          >
            Write to us · any hour · a person signs off every reply
          </p>
          <div
            className="flex items-end gap-4 border-b-2 border-[var(--ink)] pb-3 rise"
            style={{ "--i": 1 } as React.CSSProperties}
          >
            <textarea
              value={line}
              rows={1}
              onChange={(e) => {
                setLine(e.target.value);
                // grow with the text: Enter starts, Shift+Enter adds a line
                e.target.style.height = "auto";
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  start();
                }
              }}
              placeholder={`What's going on, ${user.email.split("@")[0]}?`}
              className="flex-1 bg-transparent outline-none resize-none overflow-hidden text-[42px] font-bold leading-tight placeholder:text-[#cfc7b4] caret-[var(--ox)]"
              style={{ fontFamily: "var(--font-cabinet)" }}
            />
            <button onClick={start} className="btn shrink-0 !text-[15px] !px-7 !py-3">
              Start
            </button>
          </div>
          <div className="flex flex-wrap gap-2.5 mt-4 rise" style={{ "--i": 2 } as React.CSSProperties}>
            {QUICK.map((q) => (
              <button
                key={q.label}
                onClick={() => router.push(`/new?topic=${encodeURIComponent(q.topic)}`)}
                className="chip !text-[13px] !px-4 !py-2"
              >
                {q.label.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex items-baseline gap-4 mt-16 rise" style={{ "--i": 3 } as React.CSSProperties}>
            <h2 className="text-[23px] font-bold">Your entries</h2>
            {reqs && reqs.length > 0 && (
              <span className="font-array text-[13px] text-[var(--mut)]">
                {open} OPEN{solved > 0 ? ` · ${solved} SOLVED` : ""}
              </span>
            )}
          </div>
          {!reqs ? (
            <p className="py-6 text-[var(--mut)]">Loading…</p>
          ) : reqs.length === 0 ? (
            <p className="py-6 text-[var(--mut)]">Nothing here yet. Write your first message above and it will live here.</p>
          ) : (
            <ul className="mt-1 border-t border-[var(--line)]">
              {reqs.map((r, i) => {
                const st = statusPill(r);
                const solvedRow = r.lifecycle === "resolved";
                return (
                  <li key={r.ticket_id} className="rise" style={{ "--i": i + 4 } as React.CSSProperties}>
                    <Link
                      href={`/requests/${r.ticket_id}`}
                      className={`grid grid-cols-[96px_minmax(0,1fr)_auto] gap-5 items-baseline py-5 px-1.5 border-b border-[var(--line)] hover:bg-[var(--paper-2)] hover:shadow-[inset_3px_0_0_var(--ox)] transition-all ${
                        solvedRow ? "opacity-60" : ""
                      }`}
                    >
                      <span className="font-array text-[13px] text-[var(--mut)]">
                        {new Date(r.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }).toUpperCase()}
                      </span>
                      <span className="font-semibold text-[17.5px] truncate">{r.subject}</span>
                      <span className={`font-array text-[12.5px] tracking-[0.06em] rounded-[3px] px-3 py-1.5 ${st.cls}`}>
                        {st.text}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </PortalShell>
  );
}
