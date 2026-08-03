"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CloudMark } from "@/lib/icons";
import { logout, useUser, type User } from "@/lib/useUser";

export default function PortalShell({ children }: { children: (user: User) => React.ReactNode }) {
  const { user, loading } = useUser();
  const router = useRouter();
  const [brand, setBrand] = useState({ brand_name: "Nimbus", brand_tagline: "" });

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.role !== "customer") router.replace("/workspace");
  }, [user, loading, router]);

  useEffect(() => {
    api("/config").then(setBrand).catch(() => {});
  }, []);

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  if (loading || !user || user.role !== "customer") {
    // never a silent blank page: the free-tier backend can take up to a minute
    // to wake from sleep, and this is what the visitor stares at meanwhile
    return (
      <main className="min-h-[100dvh] bg-[var(--paper)] flex items-center justify-center">
        <div className="text-center">
          <CloudMark size={52} className="mx-auto text-[var(--ox)] animate-pulse" />
          <p className="font-array text-[10.5px] tracking-[0.2em] text-[var(--mut)] mt-3">
            WAKING THE SERVICE UP · THIS CAN TAKE A MINUTE
          </p>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-[var(--paper)]">
      <header className="max-w-2xl mx-auto px-6 pt-10 pb-6 flex items-start">
        <Link href="/" className="flex items-center gap-3">
          <CloudMark size={38} className="text-[var(--ox)] shrink-0" />
          <span>
            <span className="block text-[20px] font-extrabold leading-none" style={{ fontFamily: "var(--font-cabinet)" }}>
              {brand.brand_name}
            </span>
            <span className="font-array text-[9.5px] tracking-[0.2em] text-[var(--mut)]">HELP CENTRE</span>
          </span>
        </Link>
        <div className="ml-auto text-right text-[12.5px] text-[var(--mut)]">
          {user.email}
          <br />
          <button onClick={signOut} className="underline underline-offset-4 hover:text-[var(--ox)]">
            Sign out
          </button>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-6 pb-16">{children(user)}</main>
    </div>
  );
}
