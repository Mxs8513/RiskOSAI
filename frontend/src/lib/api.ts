"use client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = { id: number; email: string; name: string; role: string; permissions: string[] };

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
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const fmtMoney = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const fmtTime = (iso: string) =>
  new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });

export const fmtPct = (n: number | null | undefined) =>
  n == null ? "—" : `${(n * 100).toFixed(1)}%`;
