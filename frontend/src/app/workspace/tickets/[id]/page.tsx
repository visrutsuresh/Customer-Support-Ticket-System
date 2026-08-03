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

// the channel a reply physically leaves through, mirroring api.dispatch_reply
function returnChannel(source?: string) {
  if (source === "email") return "email";
  if (source === "jira") return "Jira";
  if (source === "zendesk") return "Zendesk";
  return ""; // form/chat/voice replies stay in-app
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
  // autonomous mode returns raw model casing ("Escalate"): normalise before comparing
  const action = (s.decision.action ?? "").toLowerCase();
  const escalated = action === "escalate";
  const autoHandled = action === "auto_send";
  const channel = returnChannel(s.ticket.source);
  const messages = s.messages ?? [{ role: "customer", body: s.ticket.body }];
  const custInitials = initials(s.ticket.customer_name, s.ticket.customer_email);
  // where the machine acted: before the first agent turn. Not "first non-internal
  // after the opener": a customer follow-up can arrive before the machine replies,
  // and the pill must never sit above a customer bubble.
  const verdictAt = messages.findIndex((m) => m.role !== "customer" && m.role !== "internal");

  // the machine's move, told inside the thread where it happened
  const verdictLine = autoHandled
    ? "⚡ machine verdict: confident, replied without waiting for a human"
    : escalated
      ? `✋ machine verdict: ${s.decision.reason || "not confident"}, drafted a reply and stopped. Nothing has been sent.`
      : "";

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
    <main>
      {/* ---------- header: who, where from, and the machine's state at a glance ---------- */}
      <div className="px-8 py-4 border-b border-[var(--ink)] flex items-center gap-3.5 flex-wrap">
        <Link href="/workspace" className="font-array text-[11px] text-[var(--mut)] hover:text-[var(--ox)] shrink-0">
          ← QUEUE
        </Link>
        <span className="w-9 h-9 shrink-0 rounded-full grid place-items-center font-array text-[11px] font-bold bg-[var(--line)] text-[var(--ink)]">
          {custInitials}
        </span>
        <div className="min-w-0">
          <h1 className="text-[19px] font-bold leading-tight truncate">{s.ticket.subject}</h1>
          <div className="font-array text-[10.5px] text-[var(--mut)] flex flex-wrap gap-x-3">
            <span>{(s.ticket.customer_name ?? "unknown sender").toUpperCase()}</span>
            {s.ticket.customer_email && <span>{s.ticket.customer_email.toUpperCase()}</span>}
            <span>{id.toUpperCase()}</span>
            <span>
              CAT <b className="text-[var(--ink)] font-semibold">{(s.classification.category ?? "—").toUpperCase()}</b>
            </span>
            <span>
              PRI <b className="text-[var(--ink)] font-semibold">{(s.classification.priority ?? "—").toUpperCase()}</b>
            </span>
          </div>
        </div>
        {/* pills right-align as one group and wrap as a unit, never under the back link */}
        <div className="ml-auto shrink-0 flex items-center gap-2">
          {s.decision.assignee?.name && (
            <span className="font-array text-[10px] text-[var(--mut)]">
              ASSIGNED {s.decision.assignee.name.toUpperCase()}
            </span>
          )}
          <span className="font-array text-[10px] tracking-[0.12em] px-2.5 py-1 rounded-[3px] bg-[var(--paper-2)] border border-[var(--line)] text-[var(--ink)]">
            {channel ? `✉ ${s.ticket.source.toUpperCase()}` : (s.ticket.source ?? "—").toUpperCase()}
          </span>
          {autoHandled && (
            <span className="font-array text-[10px] tracking-[0.12em] px-2.5 py-1 rounded-[3px] bg-[var(--olive)] text-[var(--paper)]">
              ⚡ AUTO-HANDLED
            </span>
          )}
          {escalated && (
            <span className="font-array text-[10px] tracking-[0.12em] px-2.5 py-1 rounded-[3px] bg-[var(--rust)] text-[var(--paper)]">
              ✋ HELD FOR REVIEW
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_320px] items-start">
        {/* ---------- the conversation: one thread, every channel normalised into it ---------- */}
        <section className="px-7 py-6 min-h-[70vh]">
          <div className="max-w-[780px] mx-auto flex flex-col gap-4">
            {channel && (
              <p className="self-center max-w-[80%] text-center font-array text-[10px] tracking-[0.12em] text-[#6b5a2a] bg-[#f6ecd2] border border-dashed border-[#d9c58a] rounded-[10px] px-4 py-2">
                THIS CONVERSATION ARRIVED VIA {s.ticket.source.toUpperCase()}. REPLIES GO BACK THE SAME WAY.
              </p>
            )}

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
                <div key={i}>
                  {/* the verdict happened between their first message and whatever followed */}
                  {i === verdictAt && verdictLine && (
                    <p className="text-center mb-4">
                      <span className="font-array text-[10px] tracking-[0.1em] text-[var(--mut)] bg-[var(--paper)] border border-[var(--line)] rounded-full px-4 py-1.5">
                        {verdictLine.toUpperCase()}
                      </span>
                    </p>
                  )}
                  <div className={`flex gap-2.5 items-end ${mine ? "flex-row-reverse" : ""}`}>
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
                        {mine
                          ? `NIMBUS SUPPORT${channel ? ` · SENT VIA ${channel.toUpperCase()}` : ""}${
                              autoHandled && i === verdictAt ? " · ⚡ AUTO-SENT" : ""
                            }`
                          : (s.ticket.customer_name ?? "CUSTOMER").toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* no non-internal turn after the opener yet: the verdict line still needs a home */}
            {verdictAt === -1 && verdictLine && (
              <p className="text-center">
                <span className="font-array text-[10px] tracking-[0.1em] text-[var(--mut)] bg-[var(--paper)] border border-[var(--line)] rounded-full px-4 py-1.5">
                  {verdictLine.toUpperCase()}
                </span>
              </p>
            )}

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

          <div className="max-w-[780px] mx-auto mt-6">
            {!locked && (
              <div className="flex gap-2 mb-4">
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
                escalated={escalated}
                channel={channel}
                customerEmail={s.ticket.customer_email}
              />
            )}
          </div>
        </section>

        {/* ---------- right drawer: verdict detail + everything we know ---------- */}
        {/* outer div stretches so the tint and border run the full column height;
            the inner sticky keeps the content in view while the thread scrolls */}
        <div className="self-stretch border-l border-[var(--line)] bg-[var(--paper-2)]">
        <aside className="sticky top-0 px-5 py-6">
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
            <p className="font-array text-[10.5px] text-[var(--mut)] mt-2">GROUNDS: {s.decision.reason.toUpperCase()}</p>
          )}

          <div className="mt-4">
            <CustomerRail id={id} tags={tagChips} />
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
        </aside>
        </div>
      </div>
    </main>
  );
}
