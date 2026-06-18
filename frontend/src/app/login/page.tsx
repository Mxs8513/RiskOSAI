"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ScanSearch, FileCheck2, UserCheck } from "lucide-react";
import { api, setSession, startDemoSession, wakeBackend, DEMO_USERS_PUBLIC } from "@/lib/api";
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
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    // Resilient: if the backend is cold, fall back to the public demo roster so
    // the one-click accounts always render.
    api<DemoUser[]>("/auth/demo-users")
      .then((u) => setDemoUsers(u?.length ? u : DEMO_USERS_PUBLIC))
      .catch(() => setDemoUsers(DEMO_USERS_PUBLIC));
  }, []);


  async function submit(em: string, pw: string, key = "form") {
    setError(null);
    setLoading(key);
    const attempt = () =>
      api<{ token: string; user: any }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: em, password: pw }),
      });
    try {
      const res = await attempt();
      setSession(res.token, res.user);
      router.push("/overview");
      return;
    } catch (e: any) {
      // Backend is likely cold-starting. Wake it and retry a REAL login so the
      // recruiter lands on the live backend — every Risk Intelligence question
      // then hits real Claude, not seeded fallback data.
      setWaking(true);
      const awake = await wakeBackend();
      setWaking(false);
      if (awake) {
        try {
          const res = await attempt();
          setSession(res.token, res.user);
          router.push("/overview");
          return;
        } catch (err: any) {
          setError(err.message || "Login failed");
          setLoading(null);
          return;
        }
      }
      // Backend unreachable after retries — last resort so the recruiter still
      // gets in (seeded demo). Carry the clicked account's identity so the
      // console shows e.g. "Avery Chen", never a generic demo user.
      if (key !== "form") {
        const picked = demoUsers.find((u) => u.email === em);
        startDemoSession(picked ? { email: picked.email, name: picked.name, role: picked.role } : undefined);
        router.push("/overview");
        return;
      }
      setError(e.message || "Login failed — try the “Explore demo” button.");
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
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Choose a demo account below to explore the platform. Select <span className="font-medium text-ink">Admin</span> to
            view all features, including rules, metrics, audit logs, notifications, model performance, and developer tools.
          </p>

          {/* Primary CTA — one-click demo accounts */}
          {demoUsers.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {[...demoUsers].sort((a, b) => (b.role === "admin" ? 1 : 0) - (a.role === "admin" ? 1 : 0)).map((u) => {
                const isAdmin = u.role === "admin";
                return (
                  <button
                    key={u.email}
                    onClick={() => submit(u.email, "demo1234", u.email)}
                    disabled={loading !== null}
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left shadow-card",
                      "transition-[box-shadow,transform] duration-150 hover:shadow-lift active:scale-[0.99] disabled:opacity-50",
                      isAdmin ? "bg-primary-soft ring-1 ring-inset ring-primary/40" : "bg-card",
                    )}
                  >
                    <span className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                      isAdmin ? "bg-primary text-white" : "bg-gradient-to-b from-subtle to-border",
                    )}>
                      {u.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-xs font-medium">{u.name}</span>
                        {isAdmin && (
                          <span className="shrink-0 rounded-full bg-primary px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide text-white">
                            Recommended
                          </span>
                        )}
                      </span>
                      <span className="block text-[11px] text-muted">
                        {ROLE_LABEL[u.role] || u.role}{isAdmin ? " · best for the full demo" : ""}
                      </span>
                    </span>
                    {loading === u.email
                      ? <span className="text-[11px] text-muted">Signing in…</span>
                      : <ArrowRight size={14} className={cn("transition-transform duration-150 group-hover:translate-x-0.5", isAdmin ? "text-primary" : "text-faint group-hover:text-primary")} />}
                  </button>
                );
              })}
              <p className="pt-1 text-center text-[10px] text-faint">No setup required · seeded demo data · works even while the live API wakes up</p>
            </div>
          )}

          {/* Secondary — manual sign-in */}
          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" aria-hidden />
            <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-faint">Or sign in manually</p>
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
            {waking && <p className="mb-3 rounded-lg bg-primary-soft px-3 py-2 text-xs text-primary ring-1 ring-inset ring-primary/20">Waking the live backend… this can take ~30s on the free tier. Hang tight — you’ll get the real AI.</p>}
            <button
              type="submit" disabled={loading === "form"}
              className={cn(
                "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-ink",
                "transition-colors duration-150 hover:bg-subtle disabled:opacity-50",
              )}
            >
              {loading === "form" ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="mt-2.5 text-center text-[10px] text-faint">All demo accounts use the password demo1234</p>
        </div>
      </div>
    </div>
  );
}
