"use client";

import { useRouter } from "next/navigation";

export default function Actions({ id }: { id: string }) {
  const router = useRouter();

  async function act(kind: string) {
    await fetch(`http://localhost:8000/tickets/${id}/${kind}`, {
      method: "POST",
    });
    router.push("/");
  }

  return (
    <div className="flex gap-2">
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
    </div>
  );
}
