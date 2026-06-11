# Deploying RiskOS AI

Backend → **Render** (free tier) · Frontend → **Vercel** (free tier).
Total time: ~15 minutes. Deploy the backend first so you have its URL.

> **Demo-safe by design:** the deployed app runs with `SMS_ENABLED=false`
> (no Twilio calls), `MOCK_AI=true` (no Anthropic key needed), and synthetic
> seed data only. No secrets are required to deploy.

---

## 1. Backend on Render

**Option A — Blueprint (recommended):** Render dashboard → **New + → Blueprint**
→ select the `Mxs8513/RiskOSAI` repo → it reads [render.yaml](render.yaml) →
Apply. Done — skip to "After deploy".

**Option B — manual Web Service:**

| Setting | Value |
|---|---|
| Repository | `Mxs8513/RiskOSAI` |
| Root directory | `backend` |
| Runtime | Python |
| Build command | `pip install -r requirements-dev.txt && python -m scripts.train_model` |
| Start command | `python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Environment variables:

```
PYTHON_VERSION = 3.11.9
SMS_ENABLED    = false
MOCK_AI        = true
DATABASE_URL   = sqlite:///./riskos.db
JWT_SECRET     = <click "Generate" or paste any long random string>
CORS_ORIGINS   = http://localhost:3000        # update after frontend deploy
```

**Why these commands:** the ML artifact is gitignored, so the build trains it
(~1 min); the start command seeds demo data, which is **idempotent** — it
exits instantly if demo users already exist, so restarts are safe.

**After deploy:** open `https://<your-service>.onrender.com/health` — expect
`"status": "ok"`, `"ai_provider": "mock"`, and `"sms": {"provider": "disabled"}`.
The endpoint exposes only booleans, never secrets.

**Free-tier notes:** the SQLite database lives on the instance's ephemeral
disk — it reseeds fresh on every deploy (fine for a demo; swap `DATABASE_URL`
to a managed Postgres for persistence). Free services spin down after ~15 min
idle; the first request after that takes ~60s to wake.

## 2. Frontend on Vercel

Vercel dashboard → **Add New → Project** → import `Mxs8513/RiskOSAI`:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Next.js (auto-detected) |
| Build Command | `npm run build` (default) |
| Output | default |

Environment variable (the exact name matters — this is what the code reads):

```
NEXT_PUBLIC_API_URL = https://<your-service>.onrender.com
```

No trailing slash. Deploy.

## 3. Connect the two

1. Copy your Vercel URL (e.g. `https://riskos-ai.vercel.app`)
2. Render → your service → Environment → set
   `CORS_ORIGINS = https://riskos-ai.vercel.app,http://localhost:3000`
   → save (Render redeploys automatically)
3. Open the Vercel URL → log in with a demo user:

| Role | Email | Password |
|---|---|---|
| Fraud Analyst | `analyst@northstar.demo` | `demo1234` |
| Risk Manager | `manager@northstar.demo` | `demo1234` |
| Developer | `developer@northstar.demo` | `demo1234` |
| Admin | `admin@northstar.demo` | `demo1234` |

## 4. Smoke test (2 minutes)

1. `/health` on the backend → `status: ok`
2. Log in → Overview shows ~420 transactions and the AI Daily Summary
3. Live Transactions → Generate batch → new rows score and route
4. Risk Intelligence → "Generate a weekly fraud operations summary"
5. Model Performance → metrics + confusion matrix render (model trained at build)

Then follow [DEMO.md](DEMO.md) for the full 5-minute walkthrough.

## 5. Custom domain (optional, later)

Vercel → Project → Settings → Domains → add your domain and follow the DNS
instructions. Then add the new origin to `CORS_ORIGINS` on Render. The free
`*.vercel.app` URL is perfectly fine for a portfolio.

## Optional upgrades

- **Real AI text:** set `ANTHROPIC_API_KEY` on Render and remove `MOCK_AI`
  (or set it to `false`). Evidence packets, summaries, and document extraction
  switch to Claude automatically; the UI provider badge flips to `anthropic`.
- **Real SMS:** requires an upgraded (non-trial) Twilio account; set the
  `TWILIO_*` vars + `DEMO_CUSTOMER_PHONE` + `SMS_ENABLED=true`. SMS only ever
  goes to `DEMO_CUSTOMER_PHONE`.
- **Persistent data:** create a Render Postgres instance and point
  `DATABASE_URL` at it (`postgresql+psycopg2://...`); psycopg2-binary is
  already in requirements.
