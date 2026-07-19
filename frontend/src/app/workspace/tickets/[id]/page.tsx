"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import Actions from "./actions";

type Msg = { role: string; body: string };
type State = {
  ticket: { subject: string; body: string; customer_name: string | null; customer_email: string | null; source: string };
  classification: { category?: string; priority?: string };
  decision: { action?: string; reason?: string; confidence?: number; assignee?: { name?: string } | null };
  draft: { reply?: string; confidence?: number };
  messages?: Msg[];
  tags?: string[];
};

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [newTag, setNewTag] = useState("");

  const load = useCallback(() => {
    api(`/tickets/${id}`).then(setS).catch((e) => setError(String(e)));
  }, [id]);

  useEffect(load, [load]);

  async function addNote() {
    if (!note.trim()) return;
    await api(`/tickets/${id}/note`, { method: "POST", body: JSON.stringify({ body: note }) });
    setNote("");
    load();
  }

  async function addTag() {
    if (!newTag.trim()) return;
    await api(`/tickets/${id}/tags`, { method: "POST", body: JSON.stringify({ tag: newTag.trim().toLowerCase() }) });
    setNewTag("");
    load();
  }

  async function removeTag(tag: string) {
    await api(`/tickets/${id}/tags/${encodeURIComponent(tag)}`, { method: "DELETE" });
    load();
  }

  if (error) return <main className="p-8 text-[var(--rust)]">{error}</main>;
  if (!s) return <main className="p-8 text-[var(--mut)]">Loading…</main>;

  const conf = s.decision.confidence ?? s.draft.confidence;
  const who = (m: Msg) =>
    m.role === "customer" ? (s.ticket.customer_name ?? "CUSTOMER") : m.role === "internal" ? "INTERNAL NOTE" : "NIMBUS SUPPORT";

  return (
    <main className="max-w-6xl px-10 py-9">
      <Link href="/workspace" className="font-array text-[11px] text-[var(--mut)] hover:text-[var(--ox)]">
        ← BACK TO QUEUE
      </Link>

      <div className="border-b border-[var(--ink)] pb-4 mt-3 rise" style={{ "--i": 0 } as React.CSSProperties}>
        <h1 className="text-[28px] font-bold leading-tight">{s.ticket.subject}</h1>
        <div className="font-array text-[11px] text-[var(--mut)] mt-2 flex flex-wrap gap-x-5 gap-y-1">
          <span>{id.toUpperCase()}</span>
          <span>
            SOURCE <b className="text-[var(--ink)] font-semibold">{s.ticket.source?.toUpperCase()}</b>
          </span>
          <span>
            CAT <b className="text-[var(--ink)] font-semibold">{(s.classification.category ?? "—").toUpperCase()}</b>
          </span>
          <span>
            PRI <b className="text-[var(--ink)] font-semibold">{(s.classification.priority ?? "—").toUpperCase()}</b>
          </span>
          <span>
            {s.ticket.customer_name} · {s.ticket.customer_email}
          </span>
          {s.decision.assignee?.name && <span>ASSIGNED {s.decision.assignee.name.toUpperCase()}</span>}
        </div>
      </div>

      <div className="grid grid-cols-[1.6fr_1fr] gap-0 items-start">
        {/* thread */}
        <div className="border-r border-[var(--line)] py-6 pr-8 space-y-6">
          {(s.messages ?? [{ role: "customer", body: s.ticket.body }]).map((m, i) => (
            <div
              key={i}
              className={`rise ${m.role === "internal" ? "bg-[var(--paper-2)] p-4 rounded-[3px]" : ""}`}
              style={{ "--i": i + 1 } as React.CSSProperties}
            >
              <div className="font-array text-[10.5px] text-[var(--mut)] mb-1.5">{who(m).toUpperCase()}</div>
              <p
                className={`whitespace-pre-wrap text-[14.5px] max-w-[60ch] ${
                  m.role === "customer"
                    ? "border-l-2 border-[var(--ink)] pl-3.5"
                    : m.role === "agent"
                      ? "border-l-2 border-[var(--ox)] pl-3.5"
                      : ""
                }`}
              >
                {m.body}
              </p>
            </div>
          ))}
          <div className="flex gap-2 pt-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addNote()}
              placeholder="Add an internal note (customers never see these)"
              className="flex-1 bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 text-[13.5px]"
            />
            <button
              onClick={addNote}
              className="font-semibold text-[13px] text-[var(--ox)] border border-[var(--ox)] rounded-[3px] px-4 hover:bg-[var(--ox)] hover:text-[var(--paper)] transition-colors"
            >
              Note
            </button>
          </div>
        </div>

        {/* AI panel */}
        <div className="py-6 pl-8 sticky top-6 rise" style={{ "--i": 2 } as React.CSSProperties}>
          <div className="flex items-baseline gap-3">
            <h2 className="text-[18px] font-bold">Drafted reply</h2>
            <span className={`font-array text-[10.5px] ${s.decision.action === "escalate" ? "text-[var(--rust)]" : "text-[var(--olive)]"}`}>
              {(s.decision.action ?? "…").toUpperCase()}
            </span>
          </div>
          {typeof conf === "number" && (
            <div className="flex items-center gap-3 mt-4 mb-1">
              <span className="font-array text-[10.5px] text-[var(--mut)]">CONFIDENCE</span>
              <div className="flex-1 h-[3px] bg-[var(--line)]">
                <div className="h-full bg-[var(--ox)] transition-all duration-1000" style={{ width: `${conf}%` }} />
              </div>
              <span className="font-array font-semibold text-[15px]">{conf}</span>
            </div>
          )}
          {s.decision.reason && (
            <div className="font-array text-[10.5px] text-[var(--mut)] mb-3">GROUNDS: {s.decision.reason.toUpperCase()}</div>
          )}
          <Actions id={id} reply={s.draft.reply ?? ""} />
          <div className="border-t border-[var(--line)] mt-6 pt-4">
            <span className="font-array text-[10.5px] text-[var(--mut)]">TAGS</span>
            <div className="mt-2 flex flex-wrap gap-2 items-center">
              {(s.tags ?? []).map((tag) => (
                <span
                  key={tag}
                  className="font-array text-[11px] border border-[var(--line)] rounded-[2px] px-2.5 py-1 hover:border-[var(--ox)] transition-colors"
                >
                  {tag.toUpperCase()}
                  <button onClick={() => removeTag(tag)} className="ml-1.5 text-[var(--rust)]">
                    ×
                  </button>
                </span>
              ))}
              <input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTag()}
                placeholder="+ TAG"
                className="font-array text-[11px] w-20 bg-transparent border border-dashed border-[var(--line)] focus:border-[var(--ox)] rounded-[2px] px-2.5 py-1 outline-none placeholder:text-[var(--mut)]"
              />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
