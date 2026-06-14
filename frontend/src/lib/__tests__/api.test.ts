import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  api, isDemoMode, startDemoSession, clearSession,
  getApiStatus, setApiStatus, subscribeApiStatus,
} from "../api";

beforeEach(() => {
  localStorage.clear();
  setApiStatus("checking");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("demo session", () => {
  it("starts in non-demo mode by default", () => {
    expect(isDemoMode()).toBe(false);
  });

  it("enters demo mode and serves seeded data without network", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    startDemoSession();
    expect(isDemoMode()).toBe(true);

    const ov = await api<any>("/metrics/overview");
    expect(typeof ov.transactions_processed).toBe("number");
    expect(fetchSpy).not.toHaveBeenCalled(); // network never touched in demo mode
    expect(getApiStatus()).toBe("demo");
  });

  it("clearSession exits demo mode", () => {
    startDemoSession();
    clearSession();
    expect(isDemoMode()).toBe(false);
  });
});

describe("status store", () => {
  it("notifies subscribers on change", () => {
    const listener = vi.fn();
    const unsub = subscribeApiStatus(listener);
    setApiStatus("connected");
    expect(listener).toHaveBeenCalled();
    expect(getApiStatus()).toBe("connected");
    unsub();
  });
});

describe("graceful fallback (live mode)", () => {
  it("falls back to demo data when the backend network call fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));
    // not in demo mode
    const invs = await api<any[]>("/investigations?limit=4");
    expect(Array.isArray(invs)).toBe(true);
    expect(invs.length).toBeGreaterThan(0);
  });

  it("rethrows when there is no demo fallback for the path", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));
    await expect(api("/auth/login", { method: "POST" })).rejects.toThrow();
  });
});
