"use client";

import { demoResponse, hasDemoResponse, DEMO_USERS_PUBLIC } from "./demo-data";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Health probe / fallback timing. Render free-tier cold starts can take ~30–60s,
// so we probe quickly, show a "waking" state, and retry in the background while
// the app stays fully usable on demo data.
const HEALTH_TIMEOUT_MS = 4000;
const REQUEST_TIMEOUT_MS = 8000;
const WAKE_RETRIES = 8;
const WAKE_INTERVAL_MS = 4000;

export type User = { id: number; email: string; name: string; role: string; permissions: string[] };

export const DEMO_TOKEN = "demo-session";
// Believable default persona for the standalone "Explore demo" button — never a
// generic "demo" identity. Full permissions so every page is explorable.
export const DEMO_USER: User = {
  id: 1,
  email: "analyst@northstar.demo",
  name: "Avery Chen",
  role: "fraud_analyst",
  permissions: ["*"],
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("riskos_token");
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("riskos_user");
  return raw ? JSON.parse(raw) : null;
}

export function can(perm: string): boolean {
  const u = getUser();
  if (!u) return false;
  return u.permissions.includes("*") || u.permissions.includes(perm) ||
    u.permissions.includes(perm + ":limited");
}

export function setSession(token: string, user: User) {
  localStorage.setItem("riskos_token", token);
  localStorage.setItem("riskos_user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("riskos_token");
  localStorage.removeItem("riskos_user");
  localStorage.removeItem("riskos_demo");
}

// ---------------------------------------------------------------------------
// Demo mode
// ---------------------------------------------------------------------------
export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("riskos_demo") === "1";
}

/**
 * Enter the recruiter demo: a local session backed entirely by seeded data.
 * Pass a persona (e.g. the one-click account the recruiter clicked) so the
 * console shows that real identity instead of a generic "demo" user.
 */
export function startDemoSession(persona?: Partial<User>) {
  if (typeof window === "undefined") return;
  localStorage.setItem("riskos_demo", "1");
  const user: User = persona
    ? { id: persona.id ?? 1, email: persona.email ?? DEMO_USER.email, name: persona.name ?? DEMO_USER.name,
        role: persona.role ?? DEMO_USER.role, permissions: ["*"] }
    : DEMO_USER;
  setSession(DEMO_TOKEN, user);
  setApiStatus("demo");
}

// ---------------------------------------------------------------------------
// API status store (tiny external store; consumed via useApiStatus)
// ---------------------------------------------------------------------------
export type ApiStatus = "checking" | "waking" | "connected" | "demo";

let _status: ApiStatus = "checking";
const _listeners = new Set<() => void>();

export function getApiStatus(): ApiStatus {
  return _status;
}

export function setApiStatus(next: ApiStatus) {
  if (next === _status) return;
  _status = next;
  _listeners.forEach((l) => l());
}

export function subscribeApiStatus(listener: () => void): () => void {
  _listeners.add(listener);
  return () => _listeners.delete(listener);
}

/** Mark that a live request fell back to demo data (backend cold/unreachable). */
function markDemoFallback() {
  if (_status !== "connected") setApiStatus("demo");
}

// ---------------------------------------------------------------------------
// Backend health check + cold-start wake-up
// ---------------------------------------------------------------------------
async function probeHealth(timeout = HEALTH_TIMEOUT_MS): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${API_URL}/health`, { signal: controller.signal, cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

let _wakePromise: Promise<boolean> | null = null;

/**
 * Probe the backend and, if it's cold, keep retrying in the background while the
 * UI shows a non-intrusive "waking up" status. Never throws, never blocks the UI.
 * In demo mode this is a no-op that keeps the status on "demo".
 */
export function wakeBackend(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (isDemoMode()) {
    setApiStatus("demo");
    return Promise.resolve(false);
  }
  if (_wakePromise) return _wakePromise;

  _wakePromise = (async () => {
    if (_status !== "connected") setApiStatus("checking");
    if (await probeHealth()) {
      setApiStatus("connected");
      _wakePromise = null;
      return true;
    }
    // Cold start — show "waking" and retry quietly.
    setApiStatus("waking");
    for (let i = 0; i < WAKE_RETRIES; i++) {
      await new Promise((r) => setTimeout(r, WAKE_INTERVAL_MS));
      if (isDemoMode()) { _wakePromise = null; return false; }
      if (await probeHealth()) {
        setApiStatus("connected");
        _wakePromise = null;
        return true;
      }
    }
    // Gave up — app continues on demo fallback data.
    if (_status !== "connected") setApiStatus("demo");
    _wakePromise = null;
    return false;
  })();

  return _wakePromise;
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------
export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  // Demo mode: serve seeded data instantly; never touch the network.
  if (isDemoMode()) {
    setApiStatus("demo");
    return demoResponse(path, opts) as T;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...opts,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
        ...(opts.headers || {}),
      },
    });
  } catch (err) {
    // Network error or timeout — backend is likely cold/asleep.
    clearTimeout(timeout);
    if (hasDemoResponse(path, opts) && !path.startsWith("/auth/login")) {
      markDemoFallback();
      wakeBackend(); // keep trying in the background
      return demoResponse(path, opts) as T;
    }
    throw err instanceof Error ? err : new Error("Network error");
  }
  clearTimeout(timeout);

  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  // Upstream gateway errors (Render waking / proxy) — fall back gracefully.
  if (res.status >= 502 && res.status <= 504 && hasDemoResponse(path, opts) && !path.startsWith("/auth/login")) {
    markDemoFallback();
    wakeBackend();
    return demoResponse(path, opts) as T;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  setApiStatus("connected");
  return res.json();
}

// Re-export so callers can render demo accounts even if /auth/demo-users is cold.
export { DEMO_USERS_PUBLIC };

export const fmtMoney = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const fmtTime = (iso: string) =>
  new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });

export const fmtPct = (n: number | null | undefined) =>
  n == null ? "—" : `${(n * 100).toFixed(1)}%`;
