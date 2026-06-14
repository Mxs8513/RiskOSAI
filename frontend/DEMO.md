# RiskOS — Demo & Cold-Start Experience

The backend is deployed on Render's free tier, which **sleeps after inactivity** and
can take up to ~60s to wake. To keep the app feeling polished for recruiters even
during a cold start, the frontend ships a built-in demo mode and graceful fallbacks.
None of this removes authentication, RBAC, or any live API behavior — it sits *around* it.

## What a recruiter sees

1. **Login page → "Open Demo Dashboard"** (primary button). One click, no credentials,
   routes straight to the Overview on fully seeded demo data. Clearly labeled as demo.
2. **Background wake-up.** On page load the app silently pings `/health` and begins
   warming the backend. A subtle status chip shows `Checking API → Backend waking up… →
   Live API connected` (or `Demo data`). The UI never blocks on this.
3. **Graceful API fallback.** If a live request times out or the backend returns a
   gateway error (502–504) while cold, the request transparently falls back to seeded
   demo data and a calm banner explains: *"Live backend is starting. Demo data is
   available while the API wakes up."* No red errors, no blank screens.
4. **Real sign-in still works.** The existing demo accounts (password `demo1234`) and
   manual login are unchanged. When the backend is awake, everything runs live.

## How it works (files)

| File | Role |
| --- | --- |
| `src/lib/demo-data.ts` | Pure seeded data mirroring exact backend response shapes, plus `demoResponse(path)` / `hasDemoResponse(path)` resolvers. No network, no imports from `api.ts`. |
| `src/lib/api.ts` | Demo-mode session (`startDemoSession`, `isDemoMode`), AbortController timeouts, automatic fallback to `demoResponse` on network/gateway failure, and a tiny pub/sub **API status store** (`checking`/`waking`/`connected`/`demo`) with `wakeBackend()`. |
| `src/lib/use-api-status.ts` | `useApiStatus()` hook (`useSyncExternalStore`) for components. |
| `src/components/api-status.tsx` | Subtle status chip (login + shell header). |
| `src/components/demo-notice.tsx` | Calm banner shown when running on demo/fallback data. |
| `src/components/backend-prewarm.tsx` | Fires `wakeBackend()` once at app root so the cold start begins on first paint. |

## Modes

- **Demo mode** (`riskos_demo=1` in localStorage, set by "Open Demo Dashboard"):
  every `api()` call returns seeded data instantly; the network is never touched.
- **Live mode** (any real sign-in): calls hit the backend. On timeout or 502–504 the
  call falls back to demo data *for that request only* and keeps retrying the backend
  in the background, flipping the status chip to `Live API connected` once it's up.

## Configuration

Only one env var is needed — see `.env.local.example`:

```
NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com
```

No demo-specific config is required; the fallback data is bundled.

## Tests

`npm test` (Vitest) covers: the demo-data resolver returns correctly shaped data,
`hasDemoResponse` matches known paths, and demo-mode session helpers behave. Test
files live in `src/**/__tests__` and are excluded from `next build`.
