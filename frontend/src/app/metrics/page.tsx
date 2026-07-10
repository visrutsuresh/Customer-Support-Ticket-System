async function getMetrics() {
  const res = await fetch("http://localhost:8000/metrics", {
    cache: "no-store",
  });
  return res.json();
}

export default async function Metrics() {
  const m = await getMetrics();
  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-semibold mb-6">Metrics</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="border rounded-lg p-4">
          <div className="text-3xl font-bold">{m.total}</div>
          <div className="text-sm text-gray-500">Total tickets</div>
        </div>
        <div className="border rounded-lg p-4">
          <div className="text-3xl font-bold">{m.escalated}</div>
          <div className="text-sm text-gray-500">Escalated</div>
        </div>
        <div className="border rounded-lg p-4">
          <div className="text-3xl font-bold">{m.auto_resolved}</div>
          <div className="text-sm text-gray-500">Auto-resolved</div>
        </div>
      </div>
      <h2 className="text-lg font-semibold mt-8 mb-3">By category</h2>
      <ul className="space-y-2">
        {m.by_category.map((c: { category: string; n: number }) => (
          <li
            key={c.category}
            className="flex justify-between border rounded-lg p-3"
          >
            <span>{c.category}</span>
            <span className="font-medium">{c.n}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
