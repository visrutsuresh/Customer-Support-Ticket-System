"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import PortalShell from "../portal-shell";

const TOPICS = ["Billing", "An order", "My account", "Something else"];

function SysBubble({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="max-w-[86%] w-fit bg-white border border-[var(--line)] rounded-2xl rounded-bl-[5px] px-4 py-3 text-[14px] leading-relaxed">
        {children}
      </div>
      <p className="field !mb-0 mt-1 px-1">Nimbus support</p>
    </div>
  );
}

function MyBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-right">
      <div className="inline-block text-left max-w-[86%] bg-[var(--ox)] text-[var(--paper)] rounded-2xl rounded-br-[5px] px-4 py-3 text-[14px] leading-relaxed whitespace-pre-wrap">
        {children}
      </div>
      <p className="field !mb-0 mt-1 px-1">You</p>
    </div>
  );
}

// guided chat: topic -> describe -> confirm, then the request files as a normal ticket
function GuidedNewRequest() {
  const router = useRouter();
  const sp = useSearchParams();
  const [topic, setTopic] = useState(sp.get("topic") ?? "");
  const [desc, setDesc] = useState(sp.get("q") ?? "");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const prefilled = !!sp.get("q"); // the home writing line already said what happened

  const step = !topic ? "topic" : !desc ? "describe" : "confirm";
  // the ticket's subject: the first line of their own words, not a form field
  const subject = desc.split("\n")[0].slice(0, 60) || "Support request";

  async function file() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const out = await api("/tickets", {
        method: "POST",
        body: JSON.stringify({ subject, body: desc, source: "form" }),
      });
      router.push(out?.ticket_id ? `/requests/${out.ticket_id}` : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Nothing was filed, try again.");
      setBusy(false);
    }
  }

  function sendDraft() {
    if (!draft.trim()) return;
    setDesc(draft.trim());
    setDraft("");
  }

  return (
    <div className="mt-4">
      <Link href="/" className="font-array text-[12px] text-[var(--mut)] hover:text-[var(--ox)]">
        ← ALL ENTRIES
      </Link>

      <div className="flex flex-col gap-4 mt-5">
        {/* their words came first when they typed on the home writing line */}
        {prefilled && <MyBubble>{desc}</MyBubble>}

        <SysBubble>{prefilled ? "Got it. What's this about?" : "Hi. What's this about?"}</SysBubble>

        {step === "topic" ? (
          <div className="flex flex-wrap gap-2 pl-1">
            {TOPICS.map((t) => (
              <button key={t} onClick={() => setTopic(t)} className="chip">
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        ) : (
          <MyBubble>{topic}</MyBubble>
        )}

        {step !== "topic" && !prefilled && (
          <SysBubble>Tell me what happened. An order or invoice number helps us find it instantly, if you have one.</SysBubble>
        )}

        {step === "confirm" && !prefilled && <MyBubble>{desc}</MyBubble>}

        {step === "confirm" && (
          <div>
            <div className="max-w-[86%] w-fit bg-white border border-dashed border-[var(--ox)] rounded-2xl rounded-bl-[5px] px-4 py-3 text-[13.5px] leading-relaxed">
              <span className="field">Ready to file</span>
              <p>
                Topic <b>{topic.toUpperCase()}</b> · Subject <b>&ldquo;{subject}&rdquo;</b>
                <br />
                <span className="text-[var(--mut)]">We reply here, and a person signs off every answer.</span>
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <button onClick={file} disabled={busy} className="btn disabled:opacity-50">
                  {busy ? "Filing…" : "File my request"}
                </button>
                <button
                  onClick={() => {
                    setDraft(desc);
                    setDesc("");
                  }}
                  disabled={busy}
                  className="btn btn-outline disabled:opacity-50"
                >
                  Change my words
                </button>
                <button onClick={() => setTopic("")} disabled={busy} className="btn-link btn-link-mut">
                  Change topic
                </button>
              </div>
              {error && <p className="text-[13px] text-[var(--rust)] mt-2">{error}</p>}
            </div>
            <p className="field !mb-0 mt-1 px-1">Nimbus support</p>
          </div>
        )}
      </div>

      {step === "describe" && (
        <div className="border border-[var(--ox)] rounded-[10px] bg-white overflow-hidden mt-6">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
            placeholder="Describe what happened…"
            className="w-full h-28 px-4 py-3 text-[14px] leading-relaxed bg-transparent outline-none resize-y"
          />
          <div className="flex gap-3 items-center px-4 py-2.5 border-t border-[var(--line)]">
            <button onClick={sendDraft} disabled={!draft.trim()} className="btn disabled:opacity-40">
              Send
            </button>
            <span className="field !mb-0 ml-auto">Usually answered in minutes</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function NewRequest() {
  return (
    <PortalShell>
      {() => (
        <Suspense fallback={null}>
          <GuidedNewRequest />
        </Suspense>
      )}
    </PortalShell>
  );
}
