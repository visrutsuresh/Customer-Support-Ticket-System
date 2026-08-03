"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

/* Two different jobs that look similar and are not:
   LINK is a cross-reference. Both tickets stay open and stay separate.
   MERGE folds the other ticket into this one and RESOLVES it, which is why
   the button arms first. The server refuses a second merge of the same
   duplicate, so a mis-click is recoverable but noisy. */

export default function Related({
  id,
  related,
  mergedFrom,
  mergedInto,
  locked,
  onChange,
}: {
  id: string;
  related: string[];
  mergedFrom: string[];
  mergedInto: string | null;
  locked: boolean;
  onChange: () => void;
}) {
  const [other, setOther] = useState("");
  const [error, setError] = useState("");
  const [armed, setArmed] = useState(false);

  async function act(kind: "link" | "merge") {
    const target = other.trim().toUpperCase();
    setError("");
    if (!target) return;
    if (target === id.toUpperCase()) {
      setError("A ticket cannot be linked or merged with itself.");
      return;
    }
    if (kind === "merge" && !armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), 4000);
      return;
    }
    try {
      const body = kind === "merge" ? { duplicate_id: target } : { other_id: target };
      await api(`/tickets/${id}/${kind}`, { method: "POST", body: JSON.stringify(body) });
      setOther("");
      setArmed(false);
      onChange();
    } catch (e) {
      // the API's 400 detail already explains the three ways this fails
      setError(String(e).includes("400") ? `${target} could not be ${kind}ed: check the id exists and is not already merged.` : String(e));
    }
  }

  return (
    <div className="border-t border-[var(--line)] mt-6 pt-4">
      <span className="font-array text-[12px] text-[var(--mut)]">RELATED TICKETS</span>

      {mergedInto && (
        <p className="font-array text-[12px] text-[var(--rust)] mt-2">
          THIS TICKET WAS FOLDED INTO{" "}
          <Link href={`/workspace/tickets/${mergedInto}`} className="underline underline-offset-2">
            {mergedInto.toUpperCase()}
          </Link>
        </p>
      )}

      {(related.length > 0 || mergedFrom.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-2">
          {mergedFrom.map((t) => (
            <Link key={t} href={`/workspace/tickets/${t}`} className="chip" title="folded into this ticket">
              ◀ {t.toUpperCase()}
            </Link>
          ))}
          {related.map((t) => (
            <Link key={t} href={`/workspace/tickets/${t}`} className="chip" title="cross-referenced">
              ↔ {t.toUpperCase()}
            </Link>
          ))}
        </div>
      )}

      {related.length === 0 && mergedFrom.length === 0 && !mergedInto && (
        <p className="text-[12.5px] text-[var(--mut)] mt-2">Nothing linked yet.</p>
      )}

      {!locked && (
        <>
          <div className="flex gap-2 mt-3">
            <input
              value={other}
              onChange={(e) => setOther(e.target.value)}
              placeholder="Other ticket id, e.g. T-1042"
              className="input flex-1 text-[13px]"
            />
            <button onClick={() => act("link")} className="btn btn-outline" disabled={!other.trim()}>
              Link
            </button>
          </div>
          <button
            onClick={() => act("merge")}
            disabled={!other.trim()}
            className={`btn mt-2 w-full ${armed ? "btn-armed" : "btn-quiet"}`}
          >
            {armed ? "Press again: this resolves that ticket" : "Fold that ticket into this one"}
          </button>
          {error && <p className="font-array text-[12px] text-[var(--rust)] mt-2">{error}</p>}
        </>
      )}
    </div>
  );
}
