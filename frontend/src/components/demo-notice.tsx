"use client";

import { Info } from "lucide-react";
import { useApiStatus } from "@/lib/use-api-status";
import { isDemoMode } from "@/lib/api";

/**
 * Calm, non-alarming banner shown when the console is running on seeded demo
 * data — either because the recruiter opened the explicit demo, or because the
 * live backend is still waking from a cold start. Never red, never blocking.
 */
export function DemoNotice() {
  const status = useApiStatus();
  const demo = typeof window !== "undefined" && isDemoMode();

  if (!demo && status !== "demo" && status !== "waking") return null;

  const message = demo
    ? "You're viewing simulated demo data — seeded transactions, investigations, and metrics. No live backend calls are made in demo mode."
    : status === "waking"
      ? "Live backend is starting up. Demo data is shown while the API wakes — this can take up to a minute on the free tier."
      : "Live backend is unavailable right now. Showing seeded demo data so you can explore the full console.";

  return (
    <div className="mb-4 flex items-start gap-2.5 rounded-lg bg-primary-soft px-3.5 py-2.5 text-[13px] text-primary ring-1 ring-inset ring-primary/20">
      <Info size={15} className="mt-px shrink-0" />
      <p className="leading-relaxed">{message}</p>
    </div>
  );
}
