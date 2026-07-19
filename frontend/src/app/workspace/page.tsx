"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Ticket = {
  ticket_id: string;
  subject: string;
  category: string;
  priority: string;
  action: string;
  assignee: string | null;
  human_status: string;
  created_at: string;
};

export default function Queue() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () =>
      api("/tickets")
        .then(setTickets)
        .catch((e) => setError(String(e)));
    load();
    const i = setInterval(load, 4000);
    return () => clearInterval(i);
  }, []);

  if (error) return <main className="p-8 text-[var(--rust)]">{error}</main>;
  if (!tickets)
    return <main className="p-8 text-[var(--mut)]">Loading the queue…</main>;

  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-semibold mb-2">Ticket Queue</h1>
      <div className="flex gap-4 mb-6 text-sm">
        <Link
          href="/workspace/metrics"
          className="text-[var(--ox)] underline underline-offset-4"
        >
          Metrics
        </Link>
      </div>
      <ul className="space-y-3">
        {tickets.map((t) => (
          <li key={t.ticket_id}>
            <Link
              href={`/workspace/tickets/${t.ticket_id}`}
              className="block border border-[var(--line)] rounded-lg p-4 hover:bg-[var(--paper-2)]"
            >
              <div className="font-medium">{t.subject}</div>
              <div className="text-sm text-[var(--mut)]">
                {t.category} · {t.priority} · {t.action} · {t.human_status}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
