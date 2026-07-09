import Actions from "./actions";

type Ticket = {
  subject: string;
  body: string;
  customer_name: string | null;
  customer_email: string | null;
  source: string;
};

type State = {
  ticket: Ticket;
  classification: { category?: string; priority?: string };
  decision: {
    action?: string;
    reason?: string;
    assignee?: { name?: string } | null;
  };
  draft: { reply?: string };
};

async function getTicket(id: string): Promise<State> {
  const res = await fetch(`http://localhost:8000/tickets/${id}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Ticket not found");
  return res.json();
}

export default async function TicketDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const s = await getTicket(id);

  return (
    <main className="max-w-3xl mx-auto p-8 space-y-6">
      <a href="/" className="text-sm text-blue-600">
        ← Back to queue
      </a>

      <div>
        <h1 className="text-2xl font-semibold">{s.ticket.subject}</h1>
        <p className="text-sm text-gray-500">
          {s.ticket.customer_name} · {s.ticket.customer_email} · via{" "}
          {s.ticket.source}
        </p>
      </div>

      <section>
        <h2 className="font-medium mb-1">Customer message</h2>
        <p className="whitespace-pre-wrap">{s.ticket.body}</p>
      </section>

      <section className="text-sm text-gray-600">
        {s.classification.category} · {s.classification.priority} ·{" "}
        {s.decision.action}
        {s.decision.assignee && ` · assigned to ${s.decision.assignee.name}`}
      </section>

      <section>
        <h2 className="font-medium mb-1">AI drafted reply</h2>
        <div className="border rounded-lg p-4 whitespace-pre-wrap">
          {s.draft.reply}
        </div>
      </section>
      <Actions id={id} reply={s.draft.reply ?? ""} />
    </main>
  );
}
