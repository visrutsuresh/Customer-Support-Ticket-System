"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
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
    return <main className="min-h-[100dvh] bg-[var(--paper)]" />;
  }

  return (
    <div className="min-h-[100dvh] bg-[var(--paper)]">
      <header className="max-w-2xl mx-auto px-6 pt-10 pb-6 flex items-start">
        <Link href="/" className="flex items-center gap-3">
          <span className="w-9 h-9 bg-[var(--ox)] text-[var(--paper)] flex items-center justify-center text-lg rounded-[3px]">雲</span>
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
