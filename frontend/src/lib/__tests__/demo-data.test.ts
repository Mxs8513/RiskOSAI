import { describe, it, expect } from "vitest";
import { demoResponse, hasDemoResponse, DEMO_USERS_PUBLIC } from "../demo-data";

describe("demo-data resolver", () => {
  it("returns a recognizable health payload", () => {
    const h = demoResponse("/health") as any;
    expect(h.status).toBe("ok");
    expect(typeof h.environment).toBe("string");
  });

  it("returns overview metrics with the expected shape", () => {
    const ov = demoResponse("/metrics/overview") as any;
    expect(typeof ov.transactions_processed).toBe("number");
    expect(typeof ov.flagged_alerts).toBe("number");
    expect(typeof ov.reviewer_agreement_rate).toBe("number");
  });

  it("returns a non-empty investigations list", () => {
    const invs = demoResponse("/investigations") as any[];
    expect(Array.isArray(invs)).toBe(true);
    expect(invs.length).toBeGreaterThan(0);
    expect(invs[0]).toHaveProperty("investigation_id");
  });

  it("honors the limit query param", () => {
    const invs = demoResponse("/investigations?limit=3") as any[];
    expect(invs.length).toBeLessThanOrEqual(3);
  });

  it("returns a rich investigation detail for a specific id", () => {
    const list = demoResponse("/investigations") as any[];
    const id = list[0].investigation_id;
    const detail = demoResponse(`/investigations/${id}`) as any;
    expect(detail).toHaveProperty("transaction");
    expect(Array.isArray(detail.policies)).toBe(true);
    expect(Array.isArray(detail.timeline)).toBe(true);
  });

  it("returns transactions and rules", () => {
    expect((demoResponse("/transactions") as any[]).length).toBeGreaterThan(0);
    expect((demoResponse("/rules") as any[]).length).toBeGreaterThan(0);
  });

  it("returns demo users without passwords", () => {
    const users = demoResponse("/auth/demo-users") as any[];
    expect(users.length).toBe(DEMO_USERS_PUBLIC.length);
    expect(users[0]).not.toHaveProperty("password");
  });

  it("handles mutations with a safe default", () => {
    const res = demoResponse("/investigations/INV-1/review", { method: "POST" }) as any;
    expect(res).toBeTruthy();
  });

  it("hasDemoResponse recognizes known GET paths and prefixes", () => {
    expect(hasDemoResponse("/metrics/overview")).toBe(true);
    expect(hasDemoResponse("/investigations/INV-123")).toBe(true);
    expect(hasDemoResponse("/transactions/TXN-9")).toBe(true);
  });
});
