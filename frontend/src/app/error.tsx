"use client";

import { useEffect } from "react";

/**
 * Route-level error boundary. If any page throws while rendering (e.g. an
 * unexpected API shape), the recruiter sees a calm recovery card instead of a
 * blank white screen — and can retry or jump to the working demo immediately.
 */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Console render error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-soft text-primary text-xl">⚠</div>
      <div>
        <h1 className="text-lg font-semibold tracking-[-0.02em]">Something hiccuped</h1>
        <p className="mt-1 max-w-md text-sm text-muted">
          A view failed to render — usually because the live backend is still waking from a
          cold start. Retry in a moment, or open the seeded demo to explore the full console now.
        </p>
      </div>
      <div className="flex gap-2">
        <button
          onClick={reset}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] hover:bg-primary-hover"
        >
          Try again
        </button>
        <a
          href="/login"
          className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-subtle"
        >
          Back to sign in
        </a>
      </div>
    </div>
  );
}
