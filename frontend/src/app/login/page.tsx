"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ScanSearch, FileCheck2, UserCheck, Play } from "lucide-react";
import { api, setSession, startDemoSession, DEMO_USERS_PUBLIC } from "@/lib/api";
import { BrandLogo, cn } from "@/components/ui";
import { ApiStatusBadge } from "@/components/api-status";

type DemoUser = { email: string; name: string; role: string };

const ROLE_LABEL: Record<string, string> = {
  fraud_analyst: "Fraud Analyst",
  risk_manager: "Risk Manager",
  developer: "Developer",
  admin: "Admin",
};

const FEATURES = [
  { icon: ScanSearch, text: "Every transaction scored on arrival by an explainable rule engine" },
  { icon: FileCheck2, text: "AI evidence packets grounded in signals — never the final decision" },
  { icon: UserCheck, text: "Human reviewers decide; every action lands in the audit log" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    // Resilient: if the backend is cold, fall back to the public demo roster so
    // the one-click accounts always render.
    api<DemoUser[]>("/auth/demo-users")
      .then((u) => setDemoUsers(u?.length ? u : DEMO_USERS_PUBLIC))
      .catch(() => setDemoUsers(DEMO_USERS_PUBLIC));
  }, []);

  function openDemo() {
    startDemoSession();
    router.push("/overview");
  }

  async function submit(em: string, pw: string, key = "form") {
    setError(null);
    setLoading(key);
    try {
      const res = await api<{ token: string; user: any }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: em, password: pw }),
      });
      setSession(res.token, res.user);
      router.push("/overview");
    } catch (e: any) {
      setError(e.message || "Login failed");
      setLoading(null);
    }
  }

  const inputCls = cn(
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm",
    "shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-[border-color,box-shadow] duration-150",
    "placeholder:text-faint hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary",
  );

  return (
    <div className="flex min-h-screen">
      {/* Brand panel */}
      <div className="relative hidden w-[44%] flex-col justify-between overflow-hidden bg-[#09090B] p-10 text-white lg:flex">
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.13]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.35) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
            maskImage: "radial-gradient(ellipse 80% 60% at 30% 20%, black, transparent)",
          }}
        />
        <div aria-hidden className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary/25 blur-[120px]" />
        <div aria-hidden className="absolute -bottom-40 right-0 h-96 w-96 rounded-full bg-[#6366F1]/15 blur-[120px]" />

        <div className="relative flex items-center gap-2.5">
          <BrandLogo size={36} />
          <div>
            <p className="text-sm font-semibold tracking-[-0.01em]">Reach</p>
            <p className="text-[11px] text-white/50">Northstar Financial</p>
          </div>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl font-semibold leading-tight tracking-[-0.03em]">
            Fraud operations,
            <br />
            <span className="bg-gradient-to-r from-[#A5B4FC] to-[#6366F1] bg-clip-text text-transparent">
              with humans in the loop.
            </span>
          </h1>
          <ul className="mt-8 space-y-4">
            {FEATURES.map(({ icon: Icon, text }, i) => (
              <li key={i} className="flex items-start gap-3 text-[13px] leading-snug text-white/65">
                <span className="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/[0.07] ring-1 ring-inset ring-white/10">
                  <Icon size={13} className="text-[#A5B4FC]" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex items-center gap-2">
          <span className="rounded-full bg-white/[0.07] px-2.5 py-1 text-[10px] font-medium text-white/60 ring-1 ring-inset ring-white/10">
            Simulation environment
          </span>
          <span className="rounded-full bg-white/[0.07] px-2.5 py-1 text-[10px] font-medium text-white/60 ring-1 ring-inset ring-white/10">
            Synthetic data only
          </span>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center bg-bg px-4 py-10">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="mb-6 lg:hidden">
            <div className="mb-2 flex items-center gap-2">
              <BrandLogo size={32} />
              <span className="text-base font-semibold tracking-[-0.01em]">Reach</span>
            </div>
            <p className="text-xs text-muted">Northstar Financial · Simulation environment, synthetic data only</p>
          </div>

          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-xl font-semibold tracking-[-0.02em]">Sign in to the console</h2>
            <ApiStatusBadge />
          </div>
          <p className="text-xs leading-relaxed text-muted">
            Explore a live-style fraud operations demo with seeded transactions, investigations,
            risk scoring, and audit workflows.
          </p>

          {/* Primary recruiter entry — instant, no credentials, fully seeded */}
          <button
            onClick={openDemo}
            className={cn(
              "mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-sm font-medium text-white",
              "shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_1px_2px_rgba(9,9,11,0.18)]",
              "transition-[background-color,transform] duration-150 hover:bg-primary-hover active:scale-[0.98]",
              "focus-visible:shadow-focus-primary",
            )}
          >
            <Play size={15} className="fill-current" />
            Open Demo Dashboard
          </button>
          <p className="mt-2 text-center text-[10px] text-faint">
            No login required · seeded demo data · works even while the live API wakes up
          </p>

          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" aria-hidden />
            <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-faint">Or sign in</p>
            <span className="h-px flex-1 bg-border" aria-hidden />
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); submit(email, password); }}
            className="rounded-xl bg-card p-5 shadow-card"
          >
            <label htmlFor="email" className="mb-1 block text-xs font-medium text-ink">Email</label>
            <input
              id="email" type="email" autoComplete="email" className={cn(inputCls, "mb-3")}
              value={email} onChange={(e) => setEmail(e.target.value)} placeholder="analyst@northstar.demo"
            />
            <label htmlFor="password" className="mb-1 block text-xs font-medium text-ink">Password</label>
            <input
              id="password" type="password" autoComplete="current-password" className={cn(inputCls, "mb-4")}
              value={password} onChange={(e) => setPassword(e.target.value)} placeholder="demo1234"
            />
            {error && <p role="alert" className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger ring-1 ring-inset ring-danger-border">{error}</p>}
            <button
              type="submit" disabled={loading === "form"}
              className={cn(
                "w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white",
                "shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_1px_2px_rgba(9,9,11,0.18)]",
                "transition-[background-color,transform] duration-150 hover:bg-primary-hover active:scale-[0.98]",
                "focus-visible:shadow-focus-primary disabled:opacity-50",
              )}
            >
              {loading === "form" ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {demoUsers.length > 0 && (
            <div className="mt-6">
              <div className="mb-2.5 flex items-center gap-3">
                <span className="h-px flex-1 bg-border" aria-hidden />
                <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-faint">One-click demo accounts</p>
                <span className="h-px flex-1 bg-border" aria-hidden />
              </div>
              <div className="space-y-1.5">
                {demoUsers.map((u) => (
                  <button
                    key={u.email}
                    onClick={() => submit(u.email, "demo1234", u.email)}
                    disabled={loading !== null}
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-xl bg-card px-3 py-2.5 text-left shadow-card",
                      "transition-[box-shadow,transform] duration-150 hover:shadow-lift active:scale-[0.99] disabled:opacity-50",
                    )}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-subtle to-border text-[11px] font-semibold">
                      {u.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium">{u.name}</span>
                      <span className="block text-[11px] text-muted">{ROLE_LABEL[u.role] || u.role}</span>
                    </span>
                    {loading === u.email
                      ? <span className="text-[11px] text-muted">Signing in…</span>
                      : <ArrowRight size={14} className="text-faint transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-primary" />}
                  </button>
                ))}
              </div>
              <p className="mt-2.5 text-center text-[10px] text-faint">All demo accounts use the password demo1234</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
