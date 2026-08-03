"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import Actions from "./actions";
import Attachments from "./attachments";
import CustomerRail from "./customer-rail";
import Related from "./related";

type Msg = { role: string; body: string };
type State = {
  ticket: { subject: string; body: string; customer_name: string | null; customer_email: string | null; source: string };
  classification: { category?: string; priority?: string };
  decision: { action?: string; reason?: string; confidence?: number; assignee?: { name?: string } | null };
  draft: { reply?: string; confidence?: number };
  messages?: Msg[];
  tags?: string[];
  lifecycle?: string;
  human_status?: string;
  related?: string[];
  merged_from?: string[];
  merged_into?: string | null;
};

function initials(name?: string | null, email?: string | null) {
  const src = (name || email || "?").trim();
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [s, setS] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [newTag, setNewTag] = useState("");
  const [reopenArmed, setReopenArmed] = useState(false);

  const load = useCallback(() => {
    api(`/tickets/${id}`)
      .then(setS)
      .catch((e) => {
        // resolved tickets are refiled T-x -> HIST-x; follow the id to its archived twin
        if (id.startsWith("T-")) router.replace(`/workspace/tickets/HIST-${id.slice(2)}`);
        else setError(String(e));
      });
  }, [id, router]);

  useEffect(() => {
    load();
    const i = setInterval(load, 4000); // keep in sync with the other side's resolve
    return () => clearInterval(i);
  }, [load]);

  async function reopen() {
    // double confirm: first press arms, second press fires
    if (!reopenArmed) {
      setReopenArmed(true);
      setTimeout(() => setReopenArmed(false), 4000);
      return;
    }
    const out = await api(`/tickets/${id}/reopen`, { method: "POST" });
    router.replace(`/workspace/tickets/${out.ticket_id}`);
  }

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
  const locked = s.lifecycle === "resolved";
  const escalated = s.decision.action === "escalate";
  const messages = s.messages ?? [{ role: "customer", body: s.ticket.body }];
  const custInitials = initials(s.ticket.customer_name, s.ticket.customer_email);

  const tagChips = (
    <div className="flex flex-wrap gap-1.5 items-center">
      {(s.tags ?? []).map((tag) => (
        <span key={tag} className="chip">
          {tag.toUpperCase()}
          {!locked && (
            <button onClick={() => removeTag(tag)} className="ml-1.5 text-[var(--rust)]">
              ×
            </button>
          )}
        </span>
      ))}
      {!locked && (
        <input
          value={newTag}
          onChange={(e) => setNewTag(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTag()}
          placeholder="+ TAG"
          className="chip w-20 bg-transparent border-dashed focus:border-[var(--ox)] outline-none placeholder:text-[var(--mut)]"
        />
      )}
    </div>
  );

  return (
    <main className="max-w-[1500px]">
      <div className="px-8 pt-7 pb-4 border-b border-[var(--ink)]">
        <Link href="/workspace" className="font-array text-[11px] text-[var(--mut)] hover:text-[var(--ox)]">
          ← BACK TO QUEUE
        </Link>
        <h1 className="text-[26px] font-bold leading-tight mt-2">{s.ticket.subject}</h1>
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
          {s.decision.assignee?.name && <span>ASSIGNED {s.decision.assignee.name.toUpperCase()}</span>}
        </div>
      </div>

      <div className="grid grid-cols-[248px_minmax(0,1.5fr)_minmax(0,1fr)] items-start">
        {/* ---------- left: who this is ---------- */}
        <CustomerRail id={id} tags={tagChips} />

        {/* ---------- middle: the conversation, as a messaging thread ---------- */}
        <section className="border-r border-[var(--line)] px-7 py-6 min-h-[60vh]">
          <div className="flex flex-col gap-4">
            {messages.map((m, i) => {
              if (m.role === "internal") {
                // an internal note is not part of the conversation, so it does not get a
                // bubble: it sits between them as a system line the customer never sees
                return (
                  <div key={i} className="self-center max-w-[80%]">
                    <p className="font-array text-[10px] tracking-[0.14em] text-[var(--mut)] bg-[var(--paper-2)] border border-dashed border-[var(--line)] rounded-full px-3.5 py-1.5">
                      INTERNAL NOTE · {m.body.toUpperCase()}
                    </p>
                  </div>
                );
              }
              const mine = m.role !== "customer";
              return (
                <div key={i} className={`flex gap-2.5 items-end ${mine ? "flex-row-reverse" : ""}`}>
                  <span
                    className={`w-7 h-7 shrink-0 rounded-full grid place-items-center font-array text-[10px] ${
                      mine ? "bg-[var(--ox)] text-[var(--paper)]" : "bg-[var(--line)] text-[var(--ink)]"
                    }`}
                  >
                    {mine ? "NS" : custInitials}
                  </span>
                  <div className={`max-w-[74%] ${mine ? "text-right" : ""}`}>
                    <div
                      className={`inline-block text-left px-3.5 py-2.5 text-[13.6px] leading-relaxed whitespace-pre-wrap rounded-2xl ${
                        mine
                          ? "bg-[var(--ox)] text-[var(--paper)] rounded-br-[5px]"
                          : "bg-white border border-[var(--line)] rounded-bl-[5px]"
                      }`}
                    >
                      {m.body}
                    </div>
                    <span className="block font-array text-[9.5px] tracking-[0.12em] text-[var(--mut)] mt-1 px-1">
                      {mine ? "NIMBUS SUPPORT" : (s.ticket.customer_name ?? "CUSTOMER").toUpperCase()}
                    </span>
                  </div>
                </div>
              );
            })}

            {/* the pipeline is mid-flight: the messaging-app equivalent of "typing…" */}
            {s.human_status === "processing" && (
              <div className="flex gap-2.5 items-end">
                <span className="w-7 h-7 shrink-0 rounded-full grid place-items-center font-array text-[10px] bg-[var(--ox)] text-[var(--paper)]">
                  NS
                </span>
                <div className="bg-white border border-[var(--line)] rounded-2xl rounded-bl-[5px] px-4 py-3 flex gap-1.5">
                  <i className="w-1.5 h-1.5 rounded-full bg-[var(--mut)] animate-bounce [animation-delay:0ms]" />
                  <i className="w-1.5 h-1.5 rounded-full bg-[var(--mut)] animate-bounce [animation-delay:150ms]" />
                  <i className="w-1.5 h-1.5 rounded-full bg-[var(--mut)] animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>

          {!locked && (
            <div className="flex gap-2 mt-6">
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addNote()}
                placeholder="Add an internal note (customers never see these)"
                className="input flex-1 text-[13.5px]"
              />
              <button onClick={addNote} className="btn btn-outline">
                Note
              </button>
            </div>
          )}
        </section>

        {/* ---------- right: the machine's verdict, then the composer ---------- */}
        <section className="px-6 py-6 sticky top-4">
          <span className="field">The machine&apos;s verdict</span>
          <div className="flex items-center gap-2.5">
            <span
              className={`font-array text-[10px] tracking-[0.14em] px-2.5 py-1 rounded-[3px] text-[var(--paper)] ${
                escalated ? "bg-[var(--rust)]" : "bg-[var(--olive)]"
              }`}
            >
              {(s.decision.action ?? "…").toUpperCase()}
            </span>
            {typeof conf === "number" && (
              <>
                <div className="flex-1 h-[3px] bg-[var(--line)]">
                  <div className="h-full bg-[var(--ox)] transition-all duration-1000" style={{ width: `${conf}%` }} />
                </div>
                <span className="font-array font-semibold text-[14px]">{conf}</span>
              </>
            )}
          </div>
          {s.decision.reason && (
            <p className="font-array text-[10.5px] text-[var(--mut)] mt-2">
              GROUNDS: {s.decision.reason.toUpperCase()}
            </p>
          )}

          <div className="mt-5">
            {locked ? (
              <div>
                <p className="font-array text-[11px] text-[var(--olive)]">RESOLVED · THIS TICKET IS LOCKED</p>
                <button onClick={reopen} className={`btn mt-3 ${reopenArmed ? "btn-armed" : "btn-quiet"}`}>
                  {reopenArmed ? "Press again to confirm reopen" : "Reopen ticket"}
                </button>
              </div>
            ) : (
              <Actions
                id={id}
                reply={s.draft.reply ?? ""}
                currentAssignee={s.decision.assignee?.name ?? ""}
                confidence={conf}
              />
            )}
          </div>

          <Related
            id={id}
            related={s.related ?? []}
            mergedFrom={s.merged_from ?? []}
            mergedInto={s.merged_into ?? null}
            locked={locked}
            onChange={load}
          />
          <Attachments id={id} locked={locked} />
        </section>
      </div>
    </main>
  );
}
