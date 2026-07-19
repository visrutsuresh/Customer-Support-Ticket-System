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

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  if (loading || !user || user.role === "customer") {
    return <main className="min-h-[100dvh] bg-[var(--paper)]" />;
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
        <div className="w-10 h-10 bg-[var(--ox)] text-[var(--paper)] flex items-center justify-center text-xl rounded-[3px] mb-3">
          雲
        </div>
        <div>
          <div className="text-[27px] font-extrabold leading-none" style={{ fontFamily: "var(--font-cabinet)" }}>
            {brand}
          </div>
          <div className="font-array text-[10px] tracking-[0.22em] text-[var(--mut)] mt-1">SUPPORT REGISTRY</div>
        </div>

        <nav className="mt-10 flex flex-col gap-1">
          {navItem("/workspace", "Queue", pathname === "/workspace")}
          {navItem("/workspace/metrics", "Metrics", pathname === "/workspace/metrics")}
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
