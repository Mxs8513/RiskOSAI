"use client";

import { useSyncExternalStore } from "react";
import { subscribeApiStatus, getApiStatus, type ApiStatus } from "./api";

/** Subscribe to the live API status store (checking | waking | connected | demo). */
export function useApiStatus(): ApiStatus {
  return useSyncExternalStore(subscribeApiStatus, getApiStatus, () => "checking");
}
