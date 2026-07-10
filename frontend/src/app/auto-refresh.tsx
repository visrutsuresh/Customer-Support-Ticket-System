"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AutoRefresh() {
  const router = useRouter();
  useEffect(() => {
    const i = setInterval(() => router.refresh(), 2000);
    return () => clearInterval(i);
  }, [router]);
  return null;
}
