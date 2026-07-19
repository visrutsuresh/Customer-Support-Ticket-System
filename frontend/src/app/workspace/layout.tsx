"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/lib/useUser";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.role === "customer") router.replace("/");
  }, [user, loading, router]);

  if (loading || !user || user.role === "customer") {
    return <main className="min-h-[100dvh] bg-[var(--paper)]" />;
  }
  return <>{children}</>;
}
