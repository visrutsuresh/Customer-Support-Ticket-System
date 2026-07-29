"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Template = { id: number; name: string; category: string | null };

export default function Actions({ id, reply }: { id: string; reply: string }) {
  const router = useRouter();
  const [text, setText] = useState(reply);
  const [delivery, setDelivery] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [applied, setApplied] = useState("");
  const [macroError, setMacroError] = useState("");

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
    let out = null;
    try {
      out = await api(`/tickets/${id}/${kind}`, { method: "POST" });
    } catch {
      // resolve renames the id and the page can redirect mid-flight; land on the queue either way
    }
    if (out?.delivery) {
      setDelivery(`Delivered: ${out.delivery}`); // show how it left the building before we bounce
      setTimeout(() => router.push("/workspace"), 1200);
    } else {
      router.push("/workspace");
    }
  }

  async function saveEdit() {
    await api(`/tickets/${id}/edit`, { method: "POST", body: JSON.stringify({ reply: text }) });
    router.push("/workspace");
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
        <button onClick={() => act("approve")} className="btn">
          Approve &amp; send
        </button>
        <button onClick={saveEdit} className="btn btn-outline">
          Save edit
        </button>
        <button
          onClick={() => act("reject")}
          className="text-[var(--rust)] font-semibold text-[13px] px-3 py-2.5 hover:underline underline-offset-4"
        >
          Reject
        </button>
        <button onClick={() => act("resolve")} className="btn btn-olive ml-auto">
          Mark resolved
        </button>
      </div>
      {delivery && <p className="font-array text-[11px] text-[var(--olive)] mt-3">{delivery.toUpperCase()}</p>}
    </div>
  );
}
