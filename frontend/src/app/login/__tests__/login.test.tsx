import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { isDemoMode } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

import LoginPage from "../page";

beforeEach(() => {
  localStorage.clear();
  push.mockClear();
  // Backend cold: demo-users fetch fails, page should still render.
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("cold"));
});

describe("login page", () => {
  it("renders the recruiter demo entry button", () => {
    render(<LoginPage />);
    expect(screen.getByText("Open Demo Dashboard")).toBeInTheDocument();
  });

  it("still renders the manual sign-in form when the backend is cold", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("Open Demo Dashboard starts a demo session and routes to /overview", async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByText("Open Demo Dashboard"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/overview"));
    expect(isDemoMode()).toBe(true);
  });

  it("falls back to the public demo roster when /auth/demo-users is unavailable", async () => {
    render(<LoginPage />);
    // DEMO_USERS_PUBLIC includes the analyst account name.
    await waitFor(() => expect(screen.getByText(/Avery Chen/i)).toBeInTheDocument());
  });
});
