"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

type Template = { id: number; name: string; category: string | null };

// A3: the machine PROPOSES in a suggestion card and the agent writes in a composer below.
// Nothing is pre-committed into the box, which is the honest shape for a human-in-the-loop
// gate: the draft is visibly an offer, not a decision already taken on your behalf.
export default function Actions({
  id,
  reply,
  currentAssignee = "",
  confidence,
  escalated = false,
  channel = "",
  customerEmail,
  onNote,
}: {
  id: string;
  reply: string;
  currentAssignee?: string;
  confidence?: number;
  escalated?: boolean; // the draft card only exists when the machine held back
  channel?: string; // "email" | "Jira" | "" (in-app)
  customerEmail?: string | null;
  onNote?: (body: string) => Promise<void>; // saving an internal note, owned by the page
}) {
  const router = useRouter();
  const [text, setText] = useState(""); // the composer starts EMPTY, by design
  const [mode, setMode] = useState<"reply" | "note" | "macros">("reply"); // C2: tabs decide what the box IS
  const [noteText, setNoteText] = useState("");
  const [dismissed, setDismissed] = useState(false);
  const [delivery, setDelivery] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [applied, setApplied] = useState("");
  const [macroError, setMacroError] = useState("");
  const [busy, setBusy] = useState(false);
  const [actError, setActError] = useState("");
  const { user } = useUser();
  const [assigned, setAssigned] = useState(currentAssignee);
  const [suggestion, setSuggestion] = useState(reply);

  // the ticket polls every 4s; adopt a newly generated draft unless the agent has
  // already dismissed it or started typing over it
  useEffect(() => {
    if (!dismissed && !text) setSuggestion(reply);
  }, [reply, dismissed, text]);

  useEffect(() => {
    api("/templates").then(setTemplates).catch(() => setTemplates([]));
  }, []);

  const shortName = user?.email.split("@")[0] ?? "";

  async function assignToMe() {
    if (busy || !user) return;
    setBusy(true);
    setActError("");
    try {
      await api(`/tickets/${id}/assign`, { method: "POST", body: JSON.stringify({ assignee: shortName }) });
      setAssigned(shortName);
    } catch (e) {
      setActError(`Assign failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  async function applyTemplate(templateId: number) {
    setMacroError("");
    try {
      const out = await api(`/tickets/${id}/apply-template`, {
        method: "POST",
        body: JSON.stringify({ template_id: templateId }),
      });
      setText(out.reply); // a macro is something you are about to send, so it lands in the composer
      setApplied(out.applied_template);
      setMode("reply"); // picking a macro means you are about to edit and send it
    } catch (e) {
      setMacroError(`That macro did not apply: ${e}`);
    }
  }

  async function act(kind: string) {
    if (busy) return; // a double-click must not send the customer two emails
    setBusy(true);
    setActError("");
    try {
      const out = await api(`/tickets/${id}/${kind}`, { method: "POST" });
      if (out?.delivery) {
        setDelivery(`Delivered: ${out.delivery}`);
        setTimeout(() => router.push("/workspace"), 1200);
      } else {
        router.push("/workspace");
      }
    } catch (e) {
      setActError(`That did not go through: ${e}`);
      setBusy(false);
    }
  }

  // send whatever is in the composer: save it over the stored draft first, because
  // /approve sends the STORED draft, not whatever the screen happens to show
  async function send() {
    if (busy) return;
    const body = text.trim();
    if (!body) return;
    setBusy(true);
    setActError("");
    try {
      if (body !== suggestion.trim()) {
        await api(`/tickets/${id}/edit`, { method: "POST", body: JSON.stringify({ reply: body }) });
      }
      await act("approve");
    } catch (e) {
      setActError(`Send failed: ${e}`);
      setBusy(false);
    }
  }

  async function saveNote() {
    const body = noteText.trim();
    if (!body || busy || !onNote) return;
    setBusy(true);
    setActError("");
    try {
      await onNote(body);
      setNoteText("");
      setMode("reply");
    } catch (e) {
      setActError(`Note failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  // auto-send means the machine already sent it: showing a draft then would be a lie.
  // The card exists only while the machine has held back and is waiting on a human.
  const showSuggestion = escalated && !!suggestion.trim() && !dismissed;
  const sendLabel = channel === "email" ? "Send as email ✉" : channel ? `Send as ${channel} comment` : "Send";
  const noteMode = mode === "note";

  return (
    <div>
      {showSuggestion && (
        <div className="border border-dashed border-[var(--rust)] rounded-[10px] bg-[var(--paper)] px-4 py-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="field !mb-0 !text-[var(--rust)]">Draft · waiting on you · not sent</span>
            {typeof confidence === "number" && (
              <span className="font-array text-[12px] text-[var(--mut)] ml-auto">{confidence}</span>
            )}
          </div>
          <p className="text-[13.5px] leading-relaxed whitespace-pre-wrap mt-2 max-w-[68ch]">{suggestion}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            <button onClick={() => { setText(suggestion); void send(); }} disabled={busy} className="btn disabled:opacity-50">
              Approve &amp; {sendLabel.toLowerCase()}
            </button>
            <button onClick={() => setText(suggestion)} disabled={busy} className="btn btn-outline disabled:opacity-50">
              Edit first
            </button>
            <button onClick={() => setDismissed(true)} className="btn-link btn-link-mut">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* C2: one box, tabs decide what it IS. Reply = white with macros; note = amber. */}
      <div className={`border rounded-[10px] overflow-hidden ${noteMode ? "border-[#d9c58a]" : "border-[var(--line)]"}`}>
        <div className="flex items-stretch border-b border-[var(--line)] bg-[var(--paper-2)]">
          <button
            onClick={() => setMode("reply")}
            className={`px-4 py-2 text-[12.5px] font-semibold border-r border-[var(--line)] ${
              !noteMode ? "bg-white text-[var(--ink)] shadow-[inset_0_-2px_0_var(--ox)]" : "text-[var(--mut)]"
            }`}
          >
            Reply to customer
          </button>
          <button
            onClick={() => setMode("note")}
            className={`px-4 py-2 text-[12.5px] font-semibold border-r border-[var(--line)] ${
              noteMode ? "bg-[#f6ecd2] text-[#6b5a2a] shadow-[inset_0_-2px_0_#b98a2f]" : "text-[var(--mut)]"
            }`}
          >
            Internal note
          </button>
          {templates.length > 0 && (
            <button
              onClick={() => setMode("macros")}
              className={`px-4 py-2 text-[12.5px] font-semibold border-r border-[var(--line)] ${
                mode === "macros" ? "bg-white text-[var(--ink)] shadow-[inset_0_-2px_0_var(--ox)]" : "text-[var(--mut)]"
              }`}
            >
              Macros
            </button>
          )}
        </div>

        {noteMode ? (
          <>
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add an internal note (customers never see these)…"
              className="w-full h-24 px-4 py-3 text-[13.5px] leading-relaxed bg-[#f6ecd2] outline-none resize-y placeholder:text-[#a08c55]"
            />
            <div className="flex flex-wrap gap-2 items-center px-4 py-2.5 border-t border-[#d9c58a] bg-[#f6ecd2]">
              <button onClick={saveNote} disabled={busy || !noteText.trim()} className="btn disabled:opacity-40">
                {busy ? "Working…" : "Save note"}
              </button>
              <span className="font-array text-[12px] text-[#a08c55] ml-auto">CUSTOMERS NEVER SEE NOTES</span>
            </div>
          </>
        ) : mode === "macros" ? (
          <div className="bg-white px-4 py-4">
            <span className="field">Pick a macro · it loads into the reply box for editing</span>
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
            {macroError && <p className="font-array text-[12px] text-[var(--rust)] mt-2">{macroError}</p>}
          </div>
        ) : (
          <>
            {applied && (
              <p className="font-array text-[12px] text-[var(--olive)] px-4 pt-2">
                {applied.toUpperCase()} LOADED INTO THE COMPOSER · EDIT IT BEFORE SENDING
              </p>
            )}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={escalated ? "Or write your own reply…" : "Add to the conversation…"}
              className="w-full h-28 px-4 py-3 text-[13.5px] leading-relaxed bg-transparent outline-none resize-y"
            />
            <div className="flex flex-wrap gap-2 items-center px-4 py-2.5 border-t border-[var(--line)]">
              <button onClick={send} disabled={busy || !text.trim()} className="btn disabled:opacity-40">
                {busy ? "Working…" : sendLabel}
              </button>
              <button onClick={() => act("reject")} disabled={busy} className="btn-link text-[var(--rust)]">
                Reject
              </button>
              <button
                onClick={assignToMe}
                disabled={busy || (!!assigned && assigned === shortName)}
                className="btn btn-outline ml-auto disabled:opacity-50"
              >
                {assigned
                  ? assigned === shortName
                    ? `Assigned: ${assigned.toUpperCase()}`
                    : `Take over (now: ${assigned.toUpperCase()})`
                  : "Assign to me"}
              </button>
              <button onClick={() => act("resolve")} disabled={busy} className="btn btn-olive disabled:opacity-50">
                Mark resolved
              </button>
            </div>
          </>
        )}
      </div>
      <p className="field mt-2">
        {channel === "email" && customerEmail
          ? `Replies leave as email · to: ${customerEmail}`
          : channel
            ? `Replies post back to the ${channel} ticket`
            : "Nothing sends without you"}
      </p>

      {delivery && <p className="font-array text-[12px] text-[var(--olive)] mt-3">{delivery.toUpperCase()}</p>}
      {actError && <p className="font-array text-[12px] text-[var(--rust)] mt-3">{actError.toUpperCase()}</p>}
    </div>
  );
}
