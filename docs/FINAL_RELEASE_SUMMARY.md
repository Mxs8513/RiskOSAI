# Reach — Final Release Summary

**Product name:** Reach — Fraud Operations Console
**Internal / repo codename:** RiskOS AI (backend modules, API routes, and the
GitHub repo retain this original name)
**Org (fictional):** Northstar Financial — simulation environment, synthetic data only

---

## Live URLs

| Surface | URL |
|---|---|
| Frontend (Vercel) | https://risk-osai.vercel.app |
| Backend API (Render) | https://riskos-ai-api.onrender.com |
| API health | https://riskos-ai-api.onrender.com/health |
| Repository | https://github.com/Mxs8513/RiskOSAI |

## Demo credentials (password `demo1234`)

| Role | Email |
|---|---|
| Fraud Analyst | `analyst@northstar.demo` |
| Risk Manager | `manager@northstar.demo` |
| Developer | `developer@northstar.demo` |
| Admin | `admin@northstar.demo` |

One-click demo-account buttons are on the login page.

---

## Architecture

```
Next.js 14 frontend (Vercel)
  │  REST + JWT (RBAC), NEXT_PUBLIC_API_URL → Render
  ▼
FastAPI backend (Render)
  Synthetic stream → Enrichment → Rule engine (R-001…R-007, deterministic)
        → Hybrid scoring (0.6 × ML + 0.4 × rules)
        → Automated Response Orchestrator (approve / monitor / verify / hold / escalate)
        → AI evidence agent (Claude or mock) · Policy agent (POL-001…005) · Human review
        → Notifications (Twilio SMS, disabled) · Evidence Intake (vision + cross-check)
        → Audit logs · Metrics · Safe Risk Intelligence intents
  ▼
SQLAlchemy → SQLite (ephemeral on Render free tier; reseeds on deploy)
```

The deterministic rule engine is the explainability/audit layer; ML adds learned
pattern detection; the orchestrator automates routing; humans decide Critical
cases. Every step is audit-logged.

## Key features

- Live transaction stream, scored on arrival by 7 explainable rules
- **Hybrid ML + rule scoring** with a Model Performance page (precision/recall/F1/ROC-AUC, confusion matrix)
- **Automated Response Orchestrator** — selective human-in-the-loop (~94% automation rate on seed data)
- **Safe Risk Intelligence** — NL → parameterized safe intents; never writes SQL; refuses destructive/secret/bulk requests
- AI evidence packets (grounded in structured signals), 5 deterministic policy checks
- Human-in-the-loop review with RBAC override rules, closed-loop metrics
- Notification infrastructure (templated Twilio SMS, masked phones, disabled by default)
- Evidence Intake & Cross-Check (vision extraction + deterministic reconciliation)
- Full audit log; RBAC across Analyst / Risk Manager / Developer / Admin

## Quality

- **Backend tests:** 189 passing (Twilio + Claude fully mocked, no external calls)
- **Frontend:** `tsc --noEmit` clean, production `next build` succeeds
- **CI:** GitHub Actions runs backend pytest + frontend build on every push/PR

## AI provider status

- **Active model:** Claude **Haiku 4.5** (`claude-haiku-4-5`, ~$1/$5 per MTok)
- Local + deployed run **real Claude** (`ANTHROPIC_API_KEY` set on Render dashboard only)
- Auto-falls back to the **deterministic mock provider** if no key is present — app never crashes
- Header chip + every AI report/audit event records which provider was used

## Deployment stack

| Layer | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Root `frontend/`, env `NEXT_PUBLIC_API_URL` |
| Backend | Render (free) | Blueprint `render.yaml`; build trains ML model + seeds; SQLite ephemeral |
| CI | GitHub Actions | pytest + next build |
| Secrets | Render dashboard env vars only | never committed (`.env` gitignored) |

Deployed env: `NEXT_PUBLIC_API_URL=https://riskos-ai-api.onrender.com` (Vercel);
`CORS_ORIGINS` includes the Vercel origin + localhost, `SMS_ENABLED=false`,
`MOCK_AI=false`, `ANTHROPIC_API_KEY` set in dashboard (Render).

---

## Known issues / limitations

1. **Render free-tier cold start** — backend spins down after ~15 min idle; first request takes ~60s. Open `/health` before a demo.
2. **Twilio trial limitation** — trial accounts reject free-form SMS (error 572006); the failure is captured cleanly. Real SMS needs an upgraded Twilio account. `SMS_ENABLED=false` by default.
3. **AI provider modes** — real Claude when `ANTHROPIC_API_KEY` is set; deterministic mock otherwise. Mock content is synthesized from structured signals, clearly labeled.
4. **Ephemeral database** — SQLite on Render's ephemeral disk reseeds fresh on every deploy. Swap `DATABASE_URL` to managed Postgres for persistence.
5. **Evidence Intake upload scope** — any user with `investigations` permission (analyst+) can upload a document to any investigation; there is no per-case ownership check. Uploads are validated for content type (image/*) and size (≤8 MB), but are not malware-scanned. Acceptable for a shared fraud-ops queue / demo; tighten ownership + add scanning before any real multi-tenant use.
6. **No DB migrations** — schema changes use drop-and-reseed, not migrations.

## Next recommended improvements

- Managed Postgres on Render for persistent data
- Inbound SMS YES/NO handling (completes the verification loop) once Twilio is upgraded
- Per-case ownership + file scanning on Evidence Intake
- Alembic migrations instead of drop-and-reseed
- A short demo GIF/video embedded in the README
