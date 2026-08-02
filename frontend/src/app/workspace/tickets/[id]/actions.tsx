"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

type Template = { id: number; name: string; category: string | null };

export default function Actions({
  id,
  reply,
  currentAssignee = "",
}: {
  id: string;
  reply: string;
  currentAssignee?: string;
}) {
  const router = useRouter();
  const [text, setText] = useState(reply);
  const [delivery, setDelivery] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [applied, setApplied] = useState("");
  const [macroError, setMacroError] = useState("");
  const [busy, setBusy] = useState(false);
  const [actError, setActError] = useState("");
  const { user } = useUser();
  const [assigned, setAssigned] = useState(currentAssignee); // seeded with the ticket's real assignee

  async function assignToMe() {
    if (busy || !user) return;
    setBusy(true);
    setActError("");
    try {
      const me = user.email.split("@")[0]; // matches the short names the AI writes in the column
      await api(`/tickets/${id}/assign`, { method: "POST", body: JSON.stringify({ assignee: me }) });
      setAssigned(me);
    } catch (e) {
      setActError(`Assign failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    // staff-only endpoint, and this strip only ever renders for staff
    api("/templates").then(setTemplates).catch(() => setTemplates([]));
  }, []);

  async function applyTemplate(templateId: number) {
    setMacroError("");
    try {
      // the server overwrites the stored draft and hands back the body it used,
      // so the box shows exactly what was saved rather than a local guess
      const out = await api(`/tickets/${id}/apply-template`, {
        method: "POST",
        body: JSON.stringify({ template_id: templateId }),
      });
      setText(out.reply);
      setApplied(out.applied_template);
    } catch (e) {
      setMacroError(`That macro did not apply: ${e}`);
    }
  }

  async function act(kind: string) {
    if (busy) return; // a double-click must not double-send the customer an email
    setBusy(true);
    setActError("");
    try {
      const out = await api(`/tickets/${id}/${kind}`, { method: "POST" });
      if (out?.delivery) {
        setDelivery(`Delivered: ${out.delivery}`); // show how it left the building before we bounce
        setTimeout(() => router.push("/workspace"), 1200);
      } else {
        router.push("/workspace");
      }
    } catch (e) {
      // if resolve renamed the id mid-flight the page redirect unmounts us anyway;
      // a real failure stays on screen instead of silently bouncing to the queue
      setActError(`That did not go through: ${e}`);
      setBusy(false);
    }
  }

  async function saveEdit() {
    if (busy) return;
    setBusy(true);
    setActError("");
    try {
      await api(`/tickets/${id}/edit`, { method: "POST", body: JSON.stringify({ reply: text }) });
      router.push("/workspace");
    } catch (e) {
      setActError(`Save failed: ${e}`);
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {templates.length > 0 && (
        <div className="mb-3">
          <span className="field">MACROS</span>
          <div className="flex flex-wrap gap-1.5">
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => applyTemplate(t.id)}
                title={t.category ? `${t.name} · ${t.category}` : t.name}
                className={`chip ${applied === t.name ? "chip-on" : ""}`}
              >
                {t.name.toUpperCase()}
              </button>
            ))}
          </div>
          {applied && (
            <p className="font-array text-[10.5px] text-[var(--olive)] mt-2">
              DRAFT REPLACED WITH {applied.toUpperCase()} · EDIT IT BEFORE SENDING
            </p>
          )}
          {macroError && <p className="font-array text-[10.5px] text-[var(--rust)] mt-2">{macroError}</p>}
        </div>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="input-box h-40 text-[13.5px] leading-relaxed"
      ></textarea>
      <div className="flex gap-2 mt-3">
        <button onClick={() => act("approve")} disabled={busy} className="btn disabled:opacity-50">
          {busy ? "Working…" : "Approve & send"}
        </button>
        <button onClick={saveEdit} disabled={busy} className="btn btn-outline disabled:opacity-50">
          Save edit
        </button>
        <button
          onClick={() => act("reject")}
          disabled={busy}
          className="text-[var(--rust)] font-semibold text-[13px] px-3 py-2.5 hover:underline underline-offset-4 disabled:opacity-50"
        >
          Reject
        </button>
        <button
          onClick={assignToMe}
          disabled={busy || (!!assigned && assigned === (user?.email.split("@")[0] ?? ""))}
          className="btn btn-outline ml-auto disabled:opacity-50"
        >
          {assigned
            ? assigned === (user?.email.split("@")[0] ?? "")
              ? `Assigned: ${assigned.toUpperCase()}`
              : `Take over (now: ${assigned.toUpperCase()})`
            : "Assign to me"}
        </button>
        <button onClick={() => act("resolve")} disabled={busy} className="btn btn-olive disabled:opacity-50">
          Mark resolved
        </button>
      </div>
      {delivery && <p className="font-array text-[11px] text-[var(--olive)] mt-3">{delivery.toUpperCase()}</p>}
      {actError && <p className="font-array text-[11px] text-[var(--rust)] mt-3">{actError.toUpperCase()}</p>}
    </div>
  );
}
