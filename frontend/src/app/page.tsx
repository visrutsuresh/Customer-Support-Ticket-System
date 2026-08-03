"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import PortalShell from "./portal-shell";

type Req = { ticket_id: string; subject: string; human_status: string; lifecycle: string; created_at: string };

function statusLine(r: Req): { text: string; tone: string } {
  if (r.lifecycle === "resolved") return { text: "RESOLVED", tone: "text-[var(--olive)]" };
  if (r.lifecycle === "awaiting_customer") return { text: "WE REPLIED · YOUR TURN", tone: "text-[var(--ox)]" };
  if (r.human_status === "processing") return { text: "READING YOUR MESSAGE…", tone: "text-[var(--mut)]" };
  return { text: "WITH OUR TEAM", tone: "text-[var(--mut)]" };
}

export default function PortalHome() {
  const [reqs, setReqs] = useState<Req[] | null>(null);

  useEffect(() => {
    const load = () => api("/my/tickets").then(setReqs).catch(() => setReqs([]));
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  return (
    <PortalShell>
      {() => (
        <>
          <h1 className="text-[34px] font-extrabold leading-tight mt-4 rise" style={{ "--i": 0 } as React.CSSProperties}>
            How can we help?
          </h1>
          <p className="text-[var(--mut)] mt-2 mb-8 max-w-[46ch] rise" style={{ "--i": 1 } as React.CSSProperties}>
            Write to us any hour. Our system drafts the answer, a person signs off, and the reply comes back the way you sent it.
          </p>
          <div className="card flex items-baseline rise" style={{ "--i": 2 } as React.CSSProperties}>
            <h2 className="text-[19px] font-bold">Your requests</h2>
            <Link href="/new" className="btn ml-auto">
              + New request
            </Link>
          </div>
          {!reqs ? (
            <p className="py-6 text-[var(--mut)]">Loading…</p>
          ) : reqs.length === 0 ? (
            <p className="py-6 text-[var(--mut)]">Nothing yet. When you write to us, your requests live here.</p>
          ) : (
            <ul className="mt-2">
              {reqs.map((r, i) => {
                const st = statusLine(r);
                return (
                  <li key={r.ticket_id} className="rise" style={{ "--i": i + 3 } as React.CSSProperties}>
                    <Link
                      href={`/requests/${r.ticket_id}`}
                      className="block py-4 border-b border-[var(--line)] hover:bg-[var(--paper-2)] hover:pl-3 transition-all"
                    >
                      <span className="block font-semibold text-[15.5px]">{r.subject}</span>
                      <span className={`font-array text-[12px] ${st.tone}`}>
                        {st.text} · OPENED {new Date(r.created_at).toLocaleDateString()}
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
