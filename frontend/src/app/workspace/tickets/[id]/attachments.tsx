"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api, upload } from "@/lib/api";

type Attachment = {
  id: number;
  filename: string;
  content_type: string | null;
  size: number;
  created_at: string | null;
};

const kb = (n: number) => (n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`);

export default function Attachments({ id, locked }: { id: string; locked: boolean }) {
  const [files, setFiles] = useState<Attachment[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api(`/tickets/${id}/attachments`)
      .then(setFiles)
      .catch(() => setFiles([]));
  }, [id]);

  useEffect(load, [load]);

  async function send(file: File) {
    setError("");
    setBusy(true);
    try {
      await upload(`/tickets/${id}/attachments`, file);
      load();
    } catch (e) {
      // the server states the ceiling and the allowed types in its detail; pass it through
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
      if (picker.current) picker.current.value = ""; // let the same file be re-picked after a failure
    }
  }

  return (
    <div className="border-t border-[var(--line)] mt-6 pt-4">
      <span className="font-array text-[10.5px] text-[var(--mut)]">ATTACHMENTS</span>

      {files.length > 0 ? (
        <ul className="mt-2 space-y-1.5">
          {files.map((f) => (
            <li key={f.id} className="text-[12.5px] flex items-baseline gap-2">
              <span className="font-array text-[10px] text-[var(--mut)] shrink-0">{kb(f.size)}</span>
              {/* a plain link, not a fetch: the session cookie is scoped to the host,
                  not the port, so the browser sends it to the API on :8000 by itself */}
              <a
                href={`${API_BASE}/attachments/${f.id}`}
                className="hover:text-[var(--ox)] underline underline-offset-2 truncate"
              >
                {f.filename}
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[12.5px] text-[var(--mut)] mt-2">No files on this ticket.</p>
      )}

      {!locked && (
        <>
          <input
            ref={picker}
            type="file"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && send(e.target.files[0])}
          />
          <button
            onClick={() => picker.current?.click()}
            disabled={busy}
            className="btn btn-outline mt-3 w-full"
          >
            {busy ? "Uploading…" : "+ Attach a file"}
          </button>
          <p className="font-array text-[10px] text-[var(--mut)] mt-1.5">
            IMAGES, PDF, TXT OR CSV · 5 MB MAX
          </p>
          {error && <p className="font-array text-[10.5px] text-[var(--rust)] mt-2">{error}</p>}
        </>
      )}
    </div>
  );
}
