"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function Actions({ id, reply }: { id: string; reply: string }) {
  const router = useRouter();
  const [text, setText] = useState(reply);
  const [delivery, setDelivery] = useState("");

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
