"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import Actions from "./actions";

type State = {
  ticket: {
    subject: string;
    body: string;
    customer_name: string | null;
    customer_email: string | null;
    source: string;
  };
  classification: { category?: string; priority?: string };
  decision: {
    action?: string;
    reason?: string;
    assignee?: { name?: string } | null;
  };
  draft: { reply?: string };
};

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<State | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/tickets/${id}`).then(setS).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <main className="p-8 text-[var(--rust)]">{error}</main>;
  if (!s) return <main className="p-8 text-[var(--mut)]">Loading…</main>;

  return (
    <main className="max-w-3xl mx-auto p-8 space-y-6">
      <Link href="/workspace" className="text-sm text-[var(--ox)]">← Back to queue</Link>

      <div>
        <h1 className="text-2xl font-semibold">{s.ticket.subject}</h1>
        <p className="text-sm text-[var(--mut)]">
          {s.ticket.customer_name} · {s.ticket.customer_email} · via {s.ticket.source}
        </p>
      </div>

      <section>
        <h2 className="font-medium mb-1">Customer message</h2>
        <p className="whitespace-pre-wrap">{s.ticket.body}</p>
      </section>

      <section className="text-sm text-[var(--mut)]">
        {s.classification.category} · {s.classification.priority} · {s.decision.action}
        {s.decision.assignee && ` · assigned to ${s.decision.assignee.name}`}
      </section>

      <section>
        <h2 className="font-medium mb-1">AI drafted reply</h2>
        <div className="border border-[var(--line)] rounded-lg p-4 whitespace-pre-wrap">{s.draft.reply}</div>
      </section>
      <Actions id={id} reply={s.draft.reply ?? ""} />
    </main>
  );
}
