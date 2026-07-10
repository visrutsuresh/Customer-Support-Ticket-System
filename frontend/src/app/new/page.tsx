"use client";

import { useRouter } from "next/navigation";

export default function NewTicket() {
  const router = useRouter();

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    await fetch("http://localhost:8000/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: form.get("subject"),
        body: form.get("body"),
        source: "form",
        name: form.get("name"),
        email: form.get("email"),
      }),
    });
    router.push("/");
  }
  return (
    <main className="max-w-xl mx-auto p-8 space-y-4">
      <a href="/" className="text-sm text-blue-600">
        ← Back to queue
      </a>
      <h1 className="text-2xl font-semibold">New ticket</h1>
      <form onSubmit={submit} className="space-y-3">
        <input
          name="subject"
          placeholder="Subject"
          required
          className="w-full border rounded p-2"
        />
        <textarea
          name="body"
          placeholder="Message"
          required
          className="w-full border rounded p-2 h-32"
        />
        <input
          name="name"
          placeholder="Customer name"
          className="w-full border rounded p-2"
        />
        <input
          name="email"
          placeholder="Customer email"
          className="w-full border rounded p-2"
        />
        <button className="px-4 py-2 rounded bg-green-600 text-white">
          Submit
        </button>
      </form>
    </main>
  );
}
