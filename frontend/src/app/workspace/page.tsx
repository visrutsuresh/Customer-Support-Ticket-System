"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

type Ticket = {
  ticket_id: string;
  subject: string;
  category: string | null;
  priority: string | null;
  action: string | null;
  assignee: string | null;
  human_status: string;
  lifecycle: string;
  tags: string[];
  due_at: string | null;
  sla_breached: boolean;
  source: string | null;
  preview: string | null;
  created_at: string | null;
};

const SOURCE_GLYPH: Record<string, string> = {
  email: "✉",
  jira: "◆",
  form: "▤",
  chat: "☰",
};

function slaLabel(t: Ticket): { text: string; breached: boolean } {
  if (!t.due_at) return { text: "—", breached: false };
  const ms = new Date(t.due_at).getTime() - Date.now();
  const h = Math.floor(Math.abs(ms) / 3600000);
  const m = Math.floor((Math.abs(ms) % 3600000) / 60000);
  if (t.sla_breached || ms < 0)
    return { text: `BREACHED ${h}H ${m}M`, breached: true };
  return { text: `SLA ${h}H ${m}M`, breached: false };
}

function statusView(s: string): { label: string; dot: string; pulse: boolean } {
  switch (s) {
    case "pending":
      return { label: "NEEDS REVIEW", dot: "bg-[var(--ox)]", pulse: true };
    case "processing":
      return { label: "PROCESSING", dot: "bg-[var(--mut)]", pulse: true };
    case "approved":
      return { label: "APPROVED", dot: "bg-[var(--olive)]", pulse: false };
    case "sent":
      return { label: "SENT", dot: "bg-[var(--olive)]", pulse: false };
    case "edited":
      return { label: "EDITED", dot: "bg-[var(--olive)]", pulse: false };
    case "rejected":
      return { label: "REJECTED", dot: "bg-[var(--rust)]", pulse: false };
    case "error":
      return { label: "ERROR", dot: "bg-[var(--rust)]", pulse: false };
    default:
      return { label: s.toUpperCase(), dot: "bg-[var(--mut)]", pulse: false };
  }
}

export default function Queue() {
  const { user } = useUser();
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [qInput, setQInput] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState("live");
  const [sort, setSort] = useState("newest");

  // debounce: one request when typing pauses, not one per keystroke
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (sort !== "newest") params.set("sort", sort);
    if (status) params.set("status", status);
    if (category) params.set("category", category);
    if (scope !== "live") params.set("scope", scope);
    const load = () =>
      api(`/tickets?${params}`)
        .then((data) => {
          setTickets(data);
          setError(""); // a good poll heals a bad one, the banner must not stick
        })
        .catch((e) => setError(String(e)));
    load();
    const i = setInterval(load, 4000);
    return () => clearInterval(i);
  }, [q, status, category, scope, sort]);

  return (
    <main className="max-w-[1600px] mx-auto px-10 py-9">
      {error && (
        <p className="mb-3 font-array text-[11px] text-[var(--rust)]">
          CONNECTION TROUBLE · retrying, showing the last known queue
        </p>
      )}
      <div
        className="flex items-baseline gap-4 rise"
        style={{ "--i": 0 } as React.CSSProperties}
      >
        <h1 className="text-[26px] font-bold">The Queue</h1>
        {tickets && (
          <span className="font-array text-[11px] text-[var(--mut)]">
            {tickets.length} SHOWN ·{" "}
            {tickets.filter((t) => t.human_status === "pending").length} NEED
            REVIEW
          </span>
        )}
      </div>

      <div className="flex gap-1 mt-4">
        {/* raw archive browsing is admin-only; staff reach history via the panel on a live ticket */}
        {(user?.role === "admin" ? ["live", "archive", "all"] : ["live"]).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`chip ${scope === s ? "chip-on" : ""}`}
          >
            {s.toUpperCase()}
          </button>
        ))}
      </div>

      <div
        className="flex items-center border-t border-[var(--ink)] border-b border-b-[var(--line)] mt-4 mb-1 rise"
        style={{ "--i": 1 } as React.CSSProperties}
      >
        <input
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="Search the registry"
          className="flex-1 bg-transparent outline-none py-3 text-[13.5px] placeholder:text-[var(--mut)]"
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="font-array text-[11px] text-[var(--mut)] bg-transparent border-l border-[var(--line)] px-4 py-3 outline-none"
        >
          <option value="newest">NEWEST</option>
          <option value="oldest">OLDEST</option>
          <option value="sla">SLA URGENCY</option>
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="font-array text-[11px] text-[var(--mut)] bg-transparent border-l border-[var(--line)] px-4 py-3 outline-none"
        >
          <option value="">STATUS</option>
          <option value="pending">NEEDS REVIEW</option>
          <option value="processing">PROCESSING</option>
          <option value="approved">APPROVED</option>
          <option value="sent">SENT</option>
          <option value="edited">EDITED</option>
          <option value="rejected">REJECTED</option>
          <option value="error">ERROR</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="font-array text-[11px] text-[var(--mut)] bg-transparent border-l border-[var(--line)] px-4 py-3 outline-none"
        >
          <option value="">CATEGORY</option>
          <option value="billing">BILLING</option>
          <option value="account">ACCOUNT</option>
          <option value="technical">TECHNICAL</option>
          <option value="refund">REFUND</option>
          <option value="shipping">SHIPPING</option>
          <option value="general">GENERAL</option>
        </select>
      </div>

      {!tickets ? (
        <div aria-hidden className="divide-y divide-[var(--line)]">
          {[0, 1, 2, 3].map((i) => (
            // same template as the real rows, so data landing causes no reflow jump
            <div
              key={i}
              className="animate-pulse grid grid-cols-[92px_minmax(0,1fr)_136px_72px_64px_108px] 2xl:grid-cols-[92px_minmax(0,1fr)_110px_96px_136px_72px_64px_108px] gap-4 px-1 py-4 items-center"
            >
              <span className="h-3 w-14 rounded bg-[var(--line)]" />
              <span className="h-3 max-w-md rounded bg-[var(--line)]" />
              <span className="h-3 w-16 rounded bg-[var(--line)] hidden 2xl:block" />
              <span className="h-3 w-14 rounded bg-[var(--line)] hidden 2xl:block" />
              <span className="h-3 w-20 rounded bg-[var(--line)]" />
              <span className="h-3 w-10 rounded bg-[var(--line)]" />
              <span className="h-3 w-10 rounded bg-[var(--line)]" />
              <span className="h-3 w-16 rounded bg-[var(--line)]" />
            </div>
          ))}
        </div>
      ) : tickets.length === 0 ? (
        // a filter the visitor never set must not be blamed: on a freshly
        // provisioned client the queue is empty because nobody has written in yet
        <p className="p-4 text-[var(--mut)]">
          {q || status || category || scope !== "live"
            ? "No tickets match. Clear the search or filters to see the full queue."
            : "No tickets yet. When a customer writes in, their request lands here."}
        </p>
      ) : (
        <ul>
          {/* header row: same grid as the rows, so the dashes below it read as "empty", not broken */}
          <li
            aria-hidden
            className="grid grid-cols-[92px_minmax(0,1fr)_136px_72px_64px_108px] 2xl:grid-cols-[92px_minmax(0,1fr)_110px_96px_136px_72px_64px_108px] gap-4 px-1 pt-3 pb-2 font-array text-[9.5px] tracking-[0.14em] text-[var(--mut)] border-b border-[var(--line)]"
          >
            <span>SOURCE</span>
            <span>TICKET</span>
            <span className="hidden 2xl:block">TAGS</span>
            <span className="hidden 2xl:block">ASSIGNEE</span>
            <span>STATUS</span>
            <span>PRIORITY</span>
            <span>OPENED</span>
            <span>SLA</span>
          </li>
          {tickets.map((t, idx) => {
            const st = statusView(t.human_status);
            const sla = slaLabel(t);
            return (
              <li
                key={t.ticket_id}
                className="rise"
                style={{ "--i": idx + 2 } as React.CSSProperties}
              >
                <Link
                  href={`/workspace/tickets/${t.ticket_id}`}
                  className="row grid-cols-[92px_minmax(0,1fr)_136px_72px_64px_108px] 2xl:grid-cols-[92px_minmax(0,1fr)_110px_96px_136px_72px_64px_108px]"
                >
                  <span className="font-array text-[10.5px] text-[var(--mut)] leading-relaxed">
                    {SOURCE_GLYPH[t.source ?? ""] ?? "▤"}{" "}
                    {(t.source ?? "?").toUpperCase()}
                    <br />
                    {t.ticket_id.slice(0, 6)}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="font-semibold text-[15.5px] truncate">{t.subject}</span>
                      {t.created_at && Date.now() - new Date(t.created_at).getTime() < 60_000 && (
                        <span className="shrink-0 font-array text-[9.5px] px-1.5 py-0.5 rounded bg-[var(--olive)] text-white">
                          NEW
                        </span>
                      )}
                    </span>
                    {t.preview && (
                      <span className="block text-[12.5px] text-[var(--mut)] mt-0.5 truncate">
                        {t.preview}…
                      </span>
                    )}
                  </span>
                  <span className="font-array text-[10.5px] text-[var(--mut)] truncate min-w-0 hidden 2xl:block">
                    {(t.tags ?? []).slice(0, 3).join(" · ").toUpperCase() || "—"}
                  </span>
                  <span className="badge truncate min-w-0 hidden 2xl:block">
                    {t.assignee ? t.assignee.toUpperCase() : "—"}
                  </span>
                  <span
                    className={`font-array text-[11px] flex items-center gap-2 ${st.label === "NEEDS REVIEW" ? "text-[var(--ox)]" : st.label === "ERROR" || st.label === "REJECTED" ? "text-[var(--rust)]" : "text-[var(--mut)]"}`}
                  >
                    <i
                      className={`w-[7px] h-[7px] rounded-full ${st.dot} ${st.pulse ? "animate-pulse" : ""}`}
                    />
                    {st.label === "PROCESSING" ? (
                      <span className="workbar w-[64px]" />
                    ) : (
                      st.label
                    )}
                  </span>
                  <span
                    className={`badge ${t.priority?.toLowerCase() === "high" ? "badge-warn" : t.priority?.toLowerCase() === "critical" ? "badge-crit justify-self-start" : ""}`}
                  >
                    {(t.priority ?? "—").toUpperCase()}
                  </span>
                  <span className="font-array text-[10.5px] text-[var(--mut)] tabular-nums">
                    {t.created_at
                      ? new Date(t.created_at)
                          .toLocaleDateString("en-GB", { day: "2-digit", month: "short" })
                          .toUpperCase()
                      : "—"}
                  </span>
                  <span
                    className={`badge tabular-nums truncate min-w-0 ${sla.breached ? "badge-bad font-semibold" : ""}`}
                  >
                    {sla.text}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
