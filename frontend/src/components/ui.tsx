"use client";
import { X } from "lucide-react";
import React, { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

export function cn(...xs: (string | false | null | undefined)[]) {
  return xs.filter(Boolean).join(" ");
}

/* ---------------------------------- Card --------------------------------- */

export function Card({ children, className, hover }: {
  children: React.ReactNode; className?: string; hover?: boolean;
}) {
  return (
    <div className={cn(
      "rounded-xl bg-card shadow-card transition-shadow duration-200",
      hover && "hover:shadow-lift",
      className,
    )}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-3.5">
      <div className="min-w-0">
        <h2 className="text-[13px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xxs text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

/* ---------------------------------- Pill --------------------------------- */

type PillTone = { bg: string; text: string; ring: string; dot: string; live?: boolean };

const TONES: Record<string, PillTone> = {
  success: { bg: "bg-success-soft", text: "text-success", ring: "ring-success-border", dot: "bg-success" },
  info: { bg: "bg-info-soft", text: "text-info", ring: "ring-info-border", dot: "bg-info" },
  warn: { bg: "bg-warn-soft", text: "text-warn", ring: "ring-warn-border", dot: "bg-warn" },
  danger: { bg: "bg-danger-soft", text: "text-danger", ring: "ring-danger-border", dot: "bg-danger" },
  neutral: { bg: "bg-subtle", text: "text-muted", ring: "ring-border", dot: "bg-faint" },
};

const PILL_TONE: Record<string, keyof typeof TONES> = {
  Low: "success", Approved: "success", Cleared: "success", Passed: "success", active: "success", true_positive: "success",
  Medium: "info", Monitoring: "info", Open: "info", pending_verification: "info",
  High: "warn", "Hold for Review": "warn", "Needs Review": "warn", false_positive: "warn",
  Critical: "danger", Escalated: "danger", "Confirmed Fraud": "danger", Failed: "danger", escalated: "danger",
  disabled: "neutral",
  // Automated Response Orchestrator
  "Pending Verification": "info", "Held for Verification": "warn",
  approved: "success", monitored: "info", verification_required: "info",
  held_for_verification: "warn", escalated_to_human_review: "danger",
  not_required: "neutral", confirmed_legitimate: "success", reported_fraud: "danger", expired: "warn",
  // Notification delivery
  queued: "info", sent: "success", failed: "danger",
  // Model/rule agreement
  high: "success", medium: "warn", low: "danger",
  // Evidence cross-check verdicts
  consistent: "success", partially_consistent: "warn", inconsistent: "danger", unverifiable: "neutral",
};

const LIVE_STATES = new Set(["Open", "Monitoring"]);

export function Pill({ value, className }: { value: string | null | undefined; className?: string }) {
  if (!value) return <span className="text-xxs text-faint">—</span>;
  const tone = TONES[PILL_TONE[value] || "neutral"];
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-[3px] text-xxs font-medium ring-1 ring-inset",
      tone.bg, tone.text, tone.ring, className,
    )}>
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", tone.dot, LIVE_STATES.has(value) && "animate-pulse")} aria-hidden />
      {value.replace(/_/g, " ")}
    </span>
  );
}

/* ------------------------------- Risk score ------------------------------ */

const RISK_GRADIENT = (s: number) =>
  s >= 85 ? "from-danger to-[#F87171]" : s >= 70 ? "from-warn to-[#FBBF24]" : s >= 40 ? "from-info to-[#60A5FA]" : "from-success to-[#4ADE80]";

export function RiskScore({ score, level }: { score: number | null; level?: string | null }) {
  if (score == null) return <span className="text-xxs text-faint">—</span>;
  return (
    <div className="flex items-center gap-2" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label={`Risk score ${score}`}>
      <span className="w-7 text-right font-mono text-xs font-semibold tabular-nums">{score}</span>
      <div className="h-[5px] w-14 overflow-hidden rounded-full bg-subtle">
        <div
          className={cn("h-full origin-left rounded-full bg-gradient-to-r animate-grow-x", RISK_GRADIENT(score))}
          style={{ width: `${score}%` }}
        />
      </div>
      {level && <Pill value={level} />}
    </div>
  );
}

/* --------------------------------- Button -------------------------------- */

export function Button({ children, onClick, variant = "secondary", disabled, className, title }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; className?: string; title?: string;
  variant?: "primary" | "secondary" | "danger" | "success" | "ghost";
}) {
  const styles = {
    primary: "bg-primary text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_1px_2px_rgba(9,9,11,0.18)] hover:bg-primary-hover border-transparent",
    secondary: "bg-card text-ink border-border shadow-[0_1px_2px_rgba(9,9,11,0.04)] hover:bg-subtle hover:border-border-strong",
    danger: "bg-danger text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] hover:bg-[#B91C1C] border-transparent",
    success: "bg-success text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] hover:bg-[#15803D] border-transparent",
    ghost: "bg-transparent text-muted hover:bg-subtle hover:text-ink border-transparent",
  }[variant];
  return (
    <button
      type="button" title={title} disabled={disabled} onClick={onClick}
      className={cn(
        "inline-flex select-none items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
        "transition-[background-color,border-color,box-shadow,transform] duration-150 active:scale-[0.97]",
        "focus-visible:shadow-focus-primary disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100",
        styles, className,
      )}
    >
      {children}
    </button>
  );
}

/* -------------------------- Stat card + sparkline ------------------------- */

function useCountUp(target: number, duration = 650) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVal(target); return;
    }
    let raf = 0; const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

function AnimatedNumber({ value }: { value: string }) {
  const numMatch = value.match(/^([\d,]+(?:\.\d+)?)(.*)$/);
  const target = numMatch ? parseFloat(numMatch[1].replace(/,/g, "")) : NaN;
  const decimals = numMatch && numMatch[1].includes(".") ? numMatch[1].split(".")[1].length : 0;
  const animated = useCountUp(isNaN(target) ? 0 : target);
  if (isNaN(target)) return <>{value}</>;
  return <>{animated.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{numMatch![2]}</>;
}

export function Sparkline({ data, stroke = "#4F46E5", height = 28, width = 72 }: {
  data: number[]; stroke?: string; height?: number; width?: number;
}) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 1), min = Math.min(...data, 0);
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - 2) + 1;
    const y = height - 2 - ((v - min) / (max - min || 1)) * (height - 4);
    return `${x},${y}`;
  });
  const id = useId();
  return (
    <svg width={width} height={height} aria-hidden className="overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`1,${height - 1} ${pts.join(" ")} ${width - 1},${height - 1}`} fill={`url(#${id})`} />
      <polyline points={pts.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length - 1].split(",")[0]} cy={pts[pts.length - 1].split(",")[1]} r="2" fill={stroke} />
    </svg>
  );
}

export function StatCard({ label, value, sub, tone, delta, spark, sparkColor }: {
  label: string; value: React.ReactNode; sub?: string; tone?: "danger" | "warn" | "success";
  delta?: number | null; spark?: number[]; sparkColor?: string;
}) {
  const isStr = typeof value === "string" || typeof value === "number";
  return (
    <Card hover className="px-4 py-3.5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xxs font-medium uppercase tracking-[0.06em] text-muted">{label}</p>
        {delta != null && !isNaN(delta) && (
          <span className={cn(
            "rounded-full px-1.5 py-px font-mono text-[10px] font-medium tabular-nums ring-1 ring-inset",
            delta >= 0 ? "bg-success-soft text-success ring-success-border" : "bg-danger-soft text-danger ring-danger-border",
          )}>
            {delta >= 0 ? "+" : ""}{delta.toFixed(0)}%
          </span>
        )}
      </div>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <p className={cn(
          "text-[22px] font-semibold leading-7 tracking-[-0.02em] tabular-nums",
          tone === "danger" && "text-danger", tone === "warn" && "text-warn", tone === "success" && "text-success",
        )}>
          {isStr ? <AnimatedNumber value={String(value)} /> : value}
        </p>
        {spark && <Sparkline data={spark} stroke={sparkColor || "#4F46E5"} />}
      </div>
      {sub && <p className="mt-0.5 text-xxs text-muted">{sub}</p>}
    </Card>
  );
}

/* ---------------------------------- Table -------------------------------- */

export function Table({ head, children, empty }: { head: string[]; children: React.ReactNode; empty?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border bg-subtle/50 text-[10px] uppercase tracking-[0.08em] text-muted">
            {head.map((h) => <th key={h} scope="col" className="whitespace-nowrap px-4 py-2 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-border [&>tr]:transition-colors [&>tr]:duration-100 [&>tr:hover]:bg-subtle/60">
          {children}
        </tbody>
      </table>
      {empty && (
        <div className="px-4 py-12 text-center">
          <p className="text-xs font-medium text-muted">No records match the current filters</p>
          <p className="mt-1 text-xxs text-faint">Adjust the filters above, or generate a batch of transactions.</p>
        </div>
      )}
    </div>
  );
}

/* --------------------------------- Select -------------------------------- */

export function Select({ value, onChange, options, placeholder }: {
  value: string; onChange: (v: string) => void; options: string[]; placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value} onChange={(e) => onChange(e.target.value)} aria-label={placeholder}
        className={cn(
          "appearance-none rounded-lg border border-border bg-card py-1.5 pl-3 pr-8 text-xs text-ink",
          "shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-colors duration-150",
          "hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary",
        )}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
      </select>
      <svg aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-faint" width="12" height="12" viewBox="0 0 16 16" fill="none">
        <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

/* -------------------------------- Skeleton ------------------------------- */

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2.5 p-4" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-7 rounded-md bg-gradient-to-r from-subtle via-border/60 to-subtle bg-[length:200%_100%] animate-shimmer"
          style={{ width: `${100 - (i % 3) * 9}%` }}
        />
      ))}
    </div>
  );
}

/* --------------------------------- Drawer -------------------------------- */

export function Drawer({ open, onClose, title, children, wide }: {
  open: boolean; onClose: () => void; title: React.ReactNode; children: React.ReactNode; wide?: boolean;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true">
      <div className="absolute inset-0 animate-fade-in bg-ink/25 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div className={cn(
        "absolute right-2 top-2 bottom-2 flex flex-col overflow-hidden rounded-xl bg-card shadow-pop animate-slide-in-right",
        wide ? "w-[calc(100%-16px)] max-w-2xl" : "w-[calc(100%-16px)] max-w-lg",
      )}>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="text-[13px] font-semibold tracking-[-0.01em]">{title}</div>
          <button ref={closeRef} onClick={onClose} aria-label="Close panel"
            className="rounded-md p-1 text-muted transition-colors hover:bg-subtle hover:text-ink">
            <X size={15} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

/* ---------------------------------- Tabs --------------------------------- */

export function Tabs({ tabs, active, onChange }: { tabs: string[]; active: string; onChange: (t: string) => void }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [bar, setBar] = useState({ left: 0, width: 0 });
  useLayoutEffect(() => {
    const el = refs.current[active];
    if (el) setBar({ left: el.offsetLeft, width: el.offsetWidth });
  }, [active, tabs]);
  return (
    <div className="relative flex gap-1 border-b border-border px-5" role="tablist">
      {tabs.map((t) => (
        <button
          key={t} role="tab" aria-selected={active === t}
          ref={(el) => { refs.current[t] = el; }}
          onClick={() => onChange(t)}
          className={cn(
            "rounded-t-md px-3 py-2.5 text-xs font-medium transition-colors duration-150",
            active === t ? "text-ink" : "text-muted hover:bg-subtle/70 hover:text-ink",
          )}
        >
          {t}
        </button>
      ))}
      <span
        aria-hidden
        className="absolute bottom-[-1px] h-[2px] rounded-full bg-primary transition-[left,width] duration-200 ease-out"
        style={{ left: bar.left, width: bar.width }}
      />
    </div>
  );
}

/* ---------------------------------- Toast -------------------------------- */

export function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="status" aria-live="polite"
      className="fixed bottom-5 left-1/2 z-50 flex animate-toast-in items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-xs font-medium text-white shadow-pop"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-[#4ADE80]" aria-hidden />
      {message}
    </div>
  );
}

/* ----------------------------------- KV ---------------------------------- */

export function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-2 last:border-0">
      <span className="text-xs text-muted">{k}</span>
      <span className="text-right text-xs font-medium text-ink">{v}</span>
    </div>
  );
}

/* ----------------------------- Chart theming ----------------------------- */

export const CHART = {
  axis: { fontSize: 10.5, fill: "#A1A1AA", fontFamily: "var(--font-geist-mono)" } as const,
  grid: "#F0F0F1",
  indigo: "#4F46E5",
  indigoSoft: "#C7D2FE",
  red: "#DC2626",
  amber: "#D97706",
  green: "#16A34A",
  zinc: "#A1A1AA",
};

export function ChartTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-ink px-3 py-2 text-xxs text-white shadow-pop">
      {label != null && <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-white/50">{label}</p>}
      {payload.map((p: any) => (
        <p key={p.name} className="flex items-center gap-1.5 py-px">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color || p.fill }} aria-hidden />
          <span className="text-white/70">{p.name}:</span>
          <span className="font-medium tabular-nums">{typeof p.value === "number" ? p.value.toLocaleString() : p.value}</span>
        </p>
      ))}
    </div>
  );
}
