"use client";

import { useEffect } from "react";
import { wakeBackend } from "@/lib/api";

/**
 * Fire-and-forget backend wake-up. Mounted once near the app root so the Render
 * cold start begins the moment the page loads — before the recruiter clicks
 * anything. Never blocks rendering; failures are swallowed and surfaced only as
 * the subtle ApiStatusBadge.
 */
export function BackendPrewarm() {
  useEffect(() => {
    wakeBackend();
  }, []);
  return null;
}
