import Link from "next/link";

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

async function getTickets(): Promise<Ticket[]> {
  const res = await fetch("http://localhost:8000/tickets", {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to load tickets");
  return res.json();
}

export default async function Home() {
  const tickets = await getTickets();

  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-semibold mb-6">Ticket Queue</h1>
      <ul className="space-y-3">
        {tickets.map((t) => (
          <li key={t.ticket_id}>
          <Link
            href={`/tickets/${t.ticket_id}`}
            className="block border rounded-lg p-4 hover:bg-gray-50"
          >
            <div className="font-medium">{t.subject}</div>
            <div className="text-sm text-gray-500">
              {t.category} · {t.priority} · {t.action} · {t.human_status}
            </div>
          </Link>
        </li>
        ))}
      </ul>
    </main>
  );
}
