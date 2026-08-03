"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Profile = {
  name?: string | null;
  email?: string | null;
  plan?: string | null;
  tier?: string | null;
  account_status?: string | null;
  subscription_status?: string | null;
};
type Order = {
  order_id: string;
  item: string;
  amount: number | string | null;
  status: string | null;
  tracking: string | null;
};
type Charge = { amount: number | string | null; description: string | null; charged_at: string | null };
type Record_ = { profile: Profile | null; orders: Order[]; charges: Charge[] };
type HistoryRow = { ticket_id: string; subject: string; lifecycle: string };

// every label in this rail is `.field`, and every value sits in the same left-aligned
// column, so nothing wanders. Rows are a 2-column grid with a fixed first column, which
// is what keeps OPEN and RESOLVED from pushing their subjects out of line.
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-[var(--line)] mt-4 pt-3 first:border-0 first:mt-0 first:pt-0">
      <span className="field">{label}</span>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[74px_1fr] gap-x-2 items-baseline py-[2px]">
      <span className="font-array text-[10px] tracking-[0.1em] uppercase text-[var(--mut)]">{k}</span>
      <span className="font-array text-[11.5px] text-[var(--ink)] break-words">{v}</span>
    </div>
  );
}

function money(v: number | string | null | undefined) {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
}

export default function CustomerRail({ id, tags }: { id: string; tags: React.ReactNode }) {
  const [rec, setRec] = useState<Record_ | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);

  useEffect(() => {
    // both are need-to-know: holding this ticket open unlocks this customer, nobody else
    api(`/tickets/${id}/customer`)
      .then(setRec)
      .catch(() => setRec({ profile: null, orders: [], charges: [] }));
    api(`/tickets/${id}/history`)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [id]);

  const p = rec?.profile ?? null;

  return (
    // ponytail: no own chrome; the ticket page's right drawer supplies bg and border
    <aside>
      <Section label="Customer">
        {p ? (
          <>
            <Row k="Name" v={p.name ?? "—"} />
            <Row k="Plan" v={`${(p.plan ?? "—").toUpperCase()}${p.tier ? ` · ${p.tier.toUpperCase()}` : ""}`} />
            <Row k="Account" v={(p.account_status ?? "—").toUpperCase()} />
            {p.subscription_status && p.subscription_status !== "none" && (
              <Row k="Billing" v={p.subscription_status.replace(/_/g, " ").toUpperCase()} />
            )}
          </>
        ) : (
          // an unknown sender is normal: email and Jira tickets arrive from people
          // who were never in the CRM, and that is worth stating rather than hiding
          <p className="font-array text-[11px] text-[var(--mut)]">
            {rec ? "NOT IN THE CUSTOMER RECORDS" : "LOADING…"}
          </p>
        )}
      </Section>

      {(rec?.orders.length ?? 0) > 0 && (
        <Section label="Recent orders">
          {rec!.orders.map((o) => (
            <div key={o.order_id} className="mb-2 last:mb-0">
              <Row k={o.order_id} v={o.item} />
              <Row k="" v={`${money(o.amount)} · ${(o.status ?? "—").replace(/_/g, " ").toUpperCase()}`} />
              {o.tracking && <Row k="" v={o.tracking} />}
            </div>
          ))}
        </Section>
      )}

      {(rec?.charges.length ?? 0) > 0 && (
        <Section label="Recent charges">
          {rec!.charges.map((c, i) => (
            <Row key={i} k={money(c.amount)} v={c.description ?? "—"} />
          ))}
        </Section>
      )}

      <Section label="Tags">{tags}</Section>

      {history.length > 0 && (
        <Section label="Past tickets">
          {history.slice(0, 6).map((h) => (
            <div key={h.ticket_id} className="grid grid-cols-[74px_1fr] gap-x-2 items-baseline py-[2px]">
              <span className="font-array text-[10px] tracking-[0.1em] uppercase text-[var(--mut)]">
                {h.lifecycle === "resolved" ? "Resolved" : "Open"}
              </span>
              {h.lifecycle === "resolved" ? (
                <span className="font-array text-[11.5px] text-[var(--mut)]">{h.subject}</span>
              ) : (
                <Link
                  href={`/workspace/tickets/${h.ticket_id}`}
                  className="font-array text-[11.5px] text-[var(--ink)] hover:text-[var(--ox)] underline underline-offset-2"
                >
                  {h.subject}
                </Link>
              )}
            </div>
          ))}
        </Section>
      )}
    </aside>
  );
}
