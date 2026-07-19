"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function Actions({ id, reply }: { id: string; reply: string }) {
  const router = useRouter();
  const [text, setText] = useState(reply);
  const [delivery, setDelivery] = useState("");

  async function act(kind: string) {
    const out = await api(`/tickets/${id}/${kind}`, { method: "POST" });
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
    <div>
      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full border border-[var(--line)] rounded p-2 h-32 bg-white"
        ></textarea>
        <button onClick={() => act("approve")} className="px-4 py-2 rounded bg-[var(--olive)] text-white">
          Approve
        </button>
        <button onClick={() => act("reject")} className="px-4 py-2 rounded bg-[var(--rust)] text-white">
          Reject
        </button>
        <button onClick={saveEdit} className="px-4 py-2 rounded bg-[var(--ox)] text-white">
          Save edit
        </button>
      </div>
      {delivery && <p className="text-sm text-[var(--olive)] mt-2">{delivery}</p>}
    </div>
  );
}
