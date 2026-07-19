"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Metrics = {
  total: number;
  escalated: number;
  auto_resolved: number;
  by_category: { category: string; n: number }[];
};

export default function MetricsPage() {
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    api("/metrics").then(setM).catch(() => setM(null));
  }, []);

  if (!m) return <main className="p-8 text-[var(--mut)]">Loading…</main>;

  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-semibold mb-6">Metrics</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="border border-[var(--line)] rounded-lg p-4">
          <div className="text-3xl font-bold">{m.total}</div>
          <div className="text-sm text-[var(--mut)]">Total tickets</div>
        </div>
        <div className="border border-[var(--line)] rounded-lg p-4">
          <div className="text-3xl font-bold">{m.escalated}</div>
          <div className="text-sm text-[var(--mut)]">Escalated</div>
        </div>
        <div className="border border-[var(--line)] rounded-lg p-4">
          <div className="text-3xl font-bold">{m.auto_resolved}</div>
          <div className="text-sm text-[var(--mut)]">Auto-resolved</div>
        </div>
      </div>
      <h2 className="text-lg font-semibold mt-8 mb-3">By category</h2>
      <ul className="space-y-2">
        {m.by_category.map((c) => (
          <li key={c.category} className="flex justify-between border border-[var(--line)] rounded-lg p-3">
            <span>{c.category}</span>
            <span className="font-medium">{c.n}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
