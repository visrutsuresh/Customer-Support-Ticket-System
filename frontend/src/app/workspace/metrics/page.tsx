"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Rate = number | null;

type Metrics = {
  total: number;
  escalated: number;
  auto_resolved: number;
  avg_csat: number | null;
  csat_count: number;
  by_category: { category: string; n: number }[];
  decided: number;
  escalation_rate: Rate;
  first_contact_resolution_rate: Rate;
  resolved_count: number;
  compliance: { reviewed: number; passed: number; pass_rate: Rate; note: string };
  latency: {
    sample_size: number;
    avg_seconds: number | null;
    cold: { count: number; avg_seconds: number | null };
    warm: { count: number; avg_seconds: number | null };
    cold_threshold_seconds: number;
    note: string;
  };
  resolution_time: { sample_size: number; avg_seconds: number | null; note: string };
  cost: {
    estimate: boolean;
    gpu_seconds_measured: number;
    gpu_dollars_per_second: number;
    gpu_cost_total: number;
    priced_tickets: number;
    cost_per_ticket: number | null;
    cloud_token_cost: { available: boolean; note: string };
    note: string;
  };
  csat_improvement: { value: number; unit: string; sample: boolean; note: string };
};

const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);
const secs = (v: number | null) => (v == null ? "—" : `${v.toFixed(1)}s`);
const mins = (v: number | null) => (v == null ? "—" : `${(v / 60).toFixed(1)} min`);
const usd = (v: number | null) => (v == null ? "—" : `$${v.toFixed(4)}`);

// small pill that flags a value the user must NOT read as a hard measurement
function Badge({ kind }: { kind: "sample" | "estimate" }) {
  const label = kind === "sample" ? "sample" : "estimate";
  return (
    <span
      title={
        kind === "sample"
          ? "Illustrative placeholder, not measured from real data"
          : "Computed estimate, not a billed figure"
      }
      className="chip ml-2 rounded-full py-[1px]"
    >
      {label}
    </span>
  );
}

function Tile({
  value,
  label,
  sub,
  badge,
}: {
  value: string;
  label: string;
  sub?: string;
  badge?: "sample" | "estimate";
}) {
  return (
    <div className="panel">
      <div className="text-[30px] font-bold leading-none">{value}</div>
      <div className="text-[13px] text-[var(--mut)] flex items-center mt-1.5">
        {label}
        {badge && <Badge kind={badge} />}
      </div>
      {sub && <div className="mt-1 font-array text-[12px] text-[var(--mut)] leading-relaxed">{sub}</div>}
    </div>
  );
}

export default function PerformanceDashboard() {
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    const load = () => api("/metrics").then(setM).catch(() => {});
    load();
    // running numbers (latency / cost averages) stay truthful as volume grows: refetch on an interval
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  if (!m) return <main className="p-8 text-[var(--mut)]">Loading…</main>;

  const lat = m.latency;
  const cost = m.cost;

  return (
    <main className="max-w-5xl px-10 py-9">
      <div className="border-b border-[var(--ink)] pb-4">
        <h1 className="text-[28px] font-bold leading-tight">Performance</h1>
        <p className="font-array text-[12px] text-[var(--mut)] mt-2">
          LIVE FIGURES FROM RESOLVED TICKETS · REFRESHED EVERY 15S
        </p>
      </div>
      <div className="h-6" />

      {/* REAL: volume + decision outcomes */}
      <div className="grid grid-cols-4 gap-4">
        <Tile value={`${m.total}`} label="Total tickets" sub={`${m.resolved_count} resolved`} />
        <Tile
          value={pct(m.escalation_rate)}
          label="Escalation rate"
          sub={`${m.escalated} of ${m.decided} decided`}
        />
        <Tile
          value={pct(m.first_contact_resolution_rate)}
          label="First-contact resolution"
          sub={`${m.auto_resolved} auto-resolved`}
        />
        <Tile
          value={pct(m.compliance.pass_rate)}
          label="Compliance pass rate"
          sub={`${m.compliance.passed} of ${m.compliance.reviewed} reviewed`}
        />
      </div>

      {/* REAL: split, csat, latency, resolution time */}
      <div className="grid grid-cols-4 gap-4 mt-4">
        <Tile
          value={`${m.auto_resolved} / ${m.escalated}`}
          label="Auto-resolved / escalated"
        />
        <Tile
          value={m.avg_csat != null ? m.avg_csat.toFixed(1) : "—"}
          label={`CSAT${m.csat_count ? ` (${m.csat_count})` : ""}`}
          sub="customer rating, 1–10"
        />
        <Tile
          value={secs(lat.avg_seconds)}
          label="Avg latency / ticket"
          sub={
            lat.sample_size
              ? `${lat.sample_size} timed · cold ${secs(lat.cold.avg_seconds)} (${lat.cold.count}) / warm ${secs(lat.warm.avg_seconds)} (${lat.warm.count})`
              : "no timing data yet"
          }
        />
        <Tile
          value={mins(m.resolution_time.avg_seconds)}
          label="Avg resolution time"
          sub={
            m.resolution_time.sample_size
              ? `${m.resolution_time.sample_size} tickets with timestamps`
              : "no timestamp data yet"
          }
        />
      </div>

      {/* COST (estimate) + CSAT improvement (sample) */}
      <div className="grid grid-cols-4 gap-4 mt-4">
        <Tile
          value={usd(cost.cost_per_ticket)}
          label="GPU cost / ticket"
          badge="estimate"
          sub={`${cost.gpu_seconds_measured.toFixed(1)}s × $${cost.gpu_dollars_per_second}/s over ${cost.priced_tickets} tickets`}
        />
        <Tile
          value={usd(cost.gpu_cost_total)}
          label="GPU cost total"
          badge="estimate"
          sub="Modal T4 wall-clock, measured per run"
        />
        <Tile
          value={cost.cloud_token_cost.available ? "—" : "n/a"}
          label="Cloud token cost"
          badge="estimate"
          sub="per-ticket token counts not captured yet"
        />
        <Tile
          value={`+${m.csat_improvement.value}%`}
          label="CSAT improvement"
          badge="sample"
          sub="illustrative estimate, baseline not yet measured"
        />
      </div>

      <p className="mt-4 text-[12px] text-[var(--mut)] max-w-[80ch]">
        Cost is a labelled estimate: Modal bills GPU wall-clock time, and app-side wall-clock is used as a proxy for
        GPU-active seconds. CSAT improvement is a clearly-labelled sample, not a measured figure.
      </p>

      <h2 className="text-[19px] font-bold mt-9 pt-4 border-t border-[var(--ink)]">By category</h2>
      <ul className="mt-1">
        {m.by_category.map((c) => (
          <li key={c.category} className="grid grid-cols-[1fr_auto] items-center gap-4 py-4 px-1 border-b border-[var(--line)]">
            <span className="text-[14px]">{c.category}</span>
            <span className="font-array text-[13px] font-semibold">{c.n}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
