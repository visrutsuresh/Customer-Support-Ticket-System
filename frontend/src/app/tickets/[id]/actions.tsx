"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Actions({ id, reply }: { id: string; reply: string }) {
  const router = useRouter();
  const [text, setText] = useState(reply);

  async function act(kind: string) {
    await fetch(`http://localhost:8000/tickets/${id}/${kind}`, {
      method: "POST",
    });
    router.push("/");
  }

  async function saveEdit() {
    await fetch(`http://localhost:8000/tickets/${id}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reply: text }),
    });
    router.push("/");
  }
  return (
    <div className="flex gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full border rounded p-2 h-32"
      ></textarea>
      <button
        onClick={() => act("approve")}
        className="px-4 py-2 rounded bg-green-600 text-white"
      >
        Approve
      </button>
      <button
        onClick={() => act("reject")}
        className="px-4 py-2 rounded bg-red-600 text-white"
      >
        Reject
      </button>
      <button
        onClick={saveEdit}
        className="px-4 py-2 rounded bg-blue-600 text-white"
      >
        Save edit
      </button>
    </div>
  );
}
