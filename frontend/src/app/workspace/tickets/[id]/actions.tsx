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
    <div className="mt-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full border border-[var(--line)] focus:border-[var(--ox)] outline-none rounded-[3px] p-3 h-40 bg-[#FBF9F2] text-[13.5px] leading-relaxed"
      ></textarea>
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => act("approve")}
          className="bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-[13px] px-5 py-2.5 rounded-[3px] active:scale-[0.98] transition"
        >
          Approve &amp; send
        </button>
        <button
          onClick={saveEdit}
          className="text-[var(--ox)] border border-[var(--ox)] font-semibold text-[13px] px-4 py-2.5 rounded-[3px] hover:bg-[var(--ox)] hover:text-[var(--paper)] transition-colors"
        >
          Save edit
        </button>
        <button
          onClick={() => act("reject")}
          className="text-[var(--rust)] font-semibold text-[13px] px-3 py-2.5 hover:underline underline-offset-4"
        >
          Reject
        </button>
      </div>
      {delivery && <p className="font-array text-[11px] text-[var(--olive)] mt-3">{delivery.toUpperCase()}</p>}
    </div>
  );
}
