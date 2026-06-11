"use client";
import { API_URL, clearSession, getUser, can, User } from "@/lib/api";
import { cn } from "@/components/ui";
import {
  Activity, BarChart3, BookOpenCheck, Brain, FileSearch, LayoutDashboard, LogOut,
  MessageSquare, ScrollText, Search, Sparkles, TerminalSquare, ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect, useRef, useState } from "react";

const NAV = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard, perm: "overview" },
  { href: "/transactions", label: "Live Transactions", icon: Activity, perm: "transactions" },
  { href: "/investigations", label: "Investigations", icon: FileSearch, perm: "investigations" },
  { href: "/intelligence", label: "Risk Intelligence", icon: Sparkles, perm: "intelligence" },
  { href: "/notifications", label: "Notifications", icon: MessageSquare, perm: "transactions" },
  { href: "/rules", label: "Rules", icon: BookOpenCheck, perm: "rules" },
  { href: "/metrics", label: "Metrics", icon: BarChart3, perm: "metrics" },
  { href: "/model", label: "Model Performance", icon: Brain, perm: "overview" },
  { href: "/audit", label: "Audit Logs", icon: ScrollText, perm: "audit" },
  { href: "/developer", label: "Developer Console", icon: TerminalSquare, perm: "developer" },
];

const ROLE_LABEL: Record<string, string> = {
  fraud_analyst: "Fraud Analyst", risk_manager: "Risk Manager", developer: "Developer", admin: "Admin",
};

export default function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [aiProvider, setAiProvider] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const u = getUser();
    if (!u) { router.replace("/login"); return; }
    setUser(u);
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((h) => setAiProvider(h.ai_provider))
      .catch(() => {});
  }, [router]);

  // ⌘K / Ctrl+K focuses the global search
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!user) {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-sm text-muted">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" aria-hidden />
        Loading console…
      </div>
    );
  }

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = search.trim();
    if (!q) return;
    if (q.toLowerCase().startsWith("inv_")) router.push(`/investigations/${q}`);
    else if (q.toLowerCase().startsWith("txn_")) router.push(`/transactions?search=${q}`);
    else router.push(`/intelligence?q=${encodeURIComponent(q)}`);
    setSearch("");
  };

  const initials = user.name.split(" ").map((p) => p[0]).slice(0, 2).join("");

  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-1.5 focus:text-xs focus:text-white">
        Skip to content
      </a>

      {/* ------------------------------- Sidebar ------------------------------ */}
      <aside className="flex w-[232px] shrink-0 flex-col border-r border-border bg-card" aria-label="Primary">
        <div className="px-4 pb-3 pt-4">
          <Link href="/overview" className="flex items-center gap-2.5 rounded-lg p-1 -m-1">
            <div className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-gradient-to-b from-[#6366F1] to-primary text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_1px_3px_rgba(79,70,229,0.4)]">
              <ShieldAlert size={16} />
            </div>
            <div>
              <p className="text-[13px] font-semibold leading-tight tracking-[-0.01em]">RiskOS AI</p>
              <p className="text-[10px] leading-tight text-muted">Fraud Operations</p>
            </div>
          </Link>
        </div>

        <nav className="flex-1 space-y-px overflow-y-auto px-2.5 py-2" aria-label="Main navigation">
          {NAV.map(({ href, label, icon: Icon, perm }) => {
            const allowed = can(perm);
            const active = pathname === href || pathname.startsWith(href + "/");
            const body = (
              <span className={cn(
                "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] transition-colors duration-100",
                active ? "bg-primary-soft font-medium text-primary" : "text-muted",
                allowed && !active && "hover:bg-subtle hover:text-ink",
                !allowed && "cursor-not-allowed opacity-40",
              )}>
                {active && <span aria-hidden className="absolute left-[-10px] top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary" />}
                <Icon size={15} className={cn("shrink-0 transition-transform duration-150", allowed && !active && "group-hover:scale-110")} />
                {label}
              </span>
            );
            return allowed
              ? <Link key={href} href={href} aria-current={active ? "page" : undefined}>{body}</Link>
              : <div key={href} title="Not available for your role" aria-disabled="true">{body}</div>;
          })}
        </nav>

        <div className="border-t border-border px-3 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-subtle to-border text-[11px] font-semibold text-ink ring-2 ring-card shadow-[0_0_0_1px_rgba(9,9,11,0.06)]">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium leading-tight">{user.name}</p>
              <p className="text-[10px] leading-tight text-muted">{ROLE_LABEL[user.role] || user.role}</p>
            </div>
            <button
              onClick={() => { clearSession(); router.replace("/login"); }}
              aria-label="Sign out"
              className="rounded-md p-1.5 text-muted transition-colors duration-100 hover:bg-subtle hover:text-ink"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* ----------------------------- Main column ---------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card/80 px-5 backdrop-blur-sm">
          <span className="hidden whitespace-nowrap text-xs font-medium text-muted lg:block">
            Northstar Financial <span className="mx-1 text-faint">/</span> Fraud Operations
          </span>
          <form onSubmit={onSearch} className="relative w-full max-w-md" role="search">
            <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" aria-hidden />
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search cases and transactions, or ask RiskOS"
              placeholder="Search case, txn, or ask RiskOS…"
              className={cn(
                "w-full rounded-lg border border-border bg-subtle/70 py-1.5 pl-8 pr-12 text-xs",
                "transition-[background-color,border-color,box-shadow] duration-150",
                "placeholder:text-faint hover:border-border-strong focus:border-primary focus:bg-card focus:outline-none focus:shadow-focus-primary",
              )}
            />
            <kbd aria-hidden className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border bg-card px-1.5 py-px font-mono text-[10px] text-faint">
              ⌘K
            </kbd>
          </form>
          <div className="flex shrink-0 items-center gap-2">
            {aiProvider && (
              <span
                title="Which AI backend generates evidence packets and summaries"
                className="hidden items-center gap-1.5 rounded-full bg-subtle px-2 py-[3px] text-xxs font-medium text-muted ring-1 ring-inset ring-border md:inline-flex"
              >
                AI provider: <span className="font-mono">{aiProvider}</span>
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full bg-warn-soft px-2 py-[3px] text-xxs font-medium text-warn ring-1 ring-inset ring-warn-border">
              <span className="h-1.5 w-1.5 rounded-full bg-warn" aria-hidden />
              Simulation
            </span>
            <span className="hidden items-center gap-1.5 rounded-full bg-info-soft px-2 py-[3px] text-xxs font-medium text-info ring-1 ring-inset ring-info-border sm:inline-flex">
              Synthetic Data
            </span>
          </div>
        </header>

        <main id="main" className="flex-1 overflow-y-auto">
          <div key={pathname} className="mx-auto w-full max-w-[1480px] animate-fade-up p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-[-0.02em]">{title}</h1>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
