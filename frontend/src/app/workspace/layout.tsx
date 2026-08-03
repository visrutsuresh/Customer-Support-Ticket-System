"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { logout, useUser } from "@/lib/useUser";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const [brand, setBrand] = useState("Nimbus");
  const [syncNote, setSyncNote] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.role === "customer") router.replace("/");
  }, [user, loading, router]);

  useEffect(() => {
    api("/config").then((c) => setBrand(c.brand_name)).catch(() => {});
  }, []);

  async function syncEmail() {
    setSyncNote("SYNCING EMAIL…");
    try {
      const r = await api("/email/sync", { method: "POST" });
      setSyncNote(`EMAIL: +${r.fetched} · ${r.skipped} JUNK SKIPPED`);
    } catch {
      setSyncNote("EMAIL SYNC FAILED");
    }
  }

  async function syncJira() {
    setSyncNote("SYNCING JIRA…");
    try {
      const r = await api("/jira/sync", { method: "POST" });
      setSyncNote(`JIRA: +${r.fetched}`);
    } catch {
      setSyncNote("JIRA SYNC FAILED");
    }
  }

  async function syncZendesk() {
    setSyncNote("SYNCING ZENDESK…");
    try {
      const r = await api("/zendesk/sync", { method: "POST" });
      setSyncNote(`ZENDESK: +${r.fetched}`);
    } catch {
      setSyncNote("ZENDESK SYNC FAILED");
    }
  }

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  if (loading || !user || user.role === "customer") {
    return (
      <main className="min-h-[100dvh] bg-[var(--paper)] flex items-center justify-center">
        <p className="font-array text-[10.5px] tracking-[0.2em] text-[var(--mut)] animate-pulse">
          WAKING THE SERVICE UP · THIS CAN TAKE A MINUTE
        </p>
      </main>
    );
  }

  const navItem = (href: string, label: string, active: boolean) => (
    <Link
      href={href}
      className={`relative flex items-center gap-2 py-2 pr-4 text-[13.5px] font-medium transition-colors ${
        active
          ? "text-[var(--ink)] before:absolute before:left-[-26px] before:w-[3px] before:h-5 before:bg-[var(--ox)]"
          : "text-[var(--mut)] hover:text-[var(--ink)]"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <div className="min-h-[100dvh] bg-[var(--paper)] grid grid-cols-[210px_1fr]">
      <aside className="sticky top-0 h-[100dvh] border-r border-[var(--line)] pl-[26px] py-6 flex flex-col">
        <div className="w-10 h-10 bg-[var(--ox)] text-[var(--paper)] flex items-center justify-center rounded-[3px] mb-3">
          {/* original stylized cloud mark: lobed silhouette with an inward curl */}
          <svg viewBox="0 0 24 18" width="26" height="20" fill="currentColor" aria-label="Nimbus cloud mark">
            <path d="M6.2 14.8c-2.1 0-3.6-1.4-3.6-3.2 0-1.5 1-2.7 2.4-3.1-.1-2.2 1.6-4 3.8-4 1.4 0 2.6.7 3.3 1.8.6-1.6 2.1-2.7 3.9-2.7 2.3 0 4.2 1.8 4.2 4.1 0 .3 0 .6-.1.9 1.2.5 2 1.6 2 3 0 1.8-1.5 3.2-3.4 3.2z" />
            <circle cx="12.6" cy="10.6" r="2.5" fill="var(--ox)" />
            <path d="M12.6 8.1a2.5 2.5 0 0 1 2.5 2.5" stroke="currentColor" strokeWidth="1.1" fill="none" />
          </svg>
        </div>
        <div>
          <div className="text-[27px] font-extrabold leading-none" style={{ fontFamily: "var(--font-cabinet)" }}>
            {brand}
          </div>
          <div className="font-array text-[10px] tracking-[0.22em] text-[var(--mut)] mt-1">SUPPORT REGISTRY</div>
        </div>

        <nav className="mt-10 flex flex-col gap-1">
          {navItem("/workspace", "Queue", pathname === "/workspace")}
          {navItem("/workspace/metrics", "Performance", pathname === "/workspace/metrics")}
          <button
            onClick={syncEmail}
            className="text-left py-2 pr-4 text-[13.5px] font-medium text-[var(--mut)] hover:text-[var(--ink)] transition-colors"
          >
            Sync email
          </button>
          <button
            onClick={syncJira}
            className="text-left py-2 pr-4 text-[13.5px] font-medium text-[var(--mut)] hover:text-[var(--ink)] transition-colors"
          >
            Sync Jira
          </button>
          <button
            onClick={syncZendesk}
            className="text-left py-2 pr-4 text-[13.5px] font-medium text-[var(--mut)] hover:text-[var(--ink)] transition-colors"
          >
            Sync Zendesk
          </button>
        </nav>

        <div className="mt-auto pr-4">
          {syncNote && <div className="font-array text-[10.5px] text-[var(--mut)] mb-3">{syncNote}</div>}
          <div className="text-[13.5px] font-medium text-[var(--ink)] break-all">{user.email}</div>
          <button
            onClick={signOut}
            className="mt-1 text-[13px] text-[var(--mut)] underline underline-offset-4 hover:text-[var(--ox)]"
          >
            Sign out
          </button>
        </div>
      </aside>
      <div>{children}</div>
    </div>
  );
}
