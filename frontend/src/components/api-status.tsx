"use client";

import { useApiStatus } from "@/lib/use-api-status";
import { isDemoMode } from "@/lib/api";
import { cn } from "./ui";

type Meta = { label: string; dot: string; text: string; ring: string };

const META: Record<string, Meta> = {
  checking: {
    label: "Checking API",
    dot: "bg-slate-400",
    text: "text-slate-300",
    ring: "border-slate-700 bg-slate-800/60",
  },
  waking: {
    label: "Backend waking up…",
    dot: "bg-amber-400 animate-pulse",
    text: "text-amber-200",
    ring: "border-amber-500/40 bg-amber-500/10",
  },
  connected: {
    label: "Live API connected",
    dot: "bg-emerald-400",
    text: "text-emerald-200",
    ring: "border-emerald-500/40 bg-emerald-500/10",
  },
  demo: {
    label: "Demo data",
    dot: "bg-indigo-400",
    text: "text-indigo-200",
    ring: "border-indigo-500/40 bg-indigo-500/10",
  },
};

/**
 * Subtle, non-alarming API status indicator. Shows "Demo data" whenever the
 * recruiter demo session is active, otherwise reflects the live health probe.
 */
export function ApiStatusBadge({ className }: { className?: string }) {
  const status = useApiStatus();
  // In an explicit demo session we always present the demo label.
  const key = typeof window !== "undefined" && isDemoMode() ? "demo" : status;
  const m = META[key] ?? META.checking;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        m.ring,
        m.text,
        className,
      )}
      title={m.label}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  );
}
