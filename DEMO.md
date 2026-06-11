# RiskOS AI — 5-Minute Demo Script

Setup (once): backend `python -m scripts.seed --reset && uvicorn app.main:app`,
frontend `npm run dev`. Log in as **analyst@northstar.demo / demo1234**.

## 1. Overview (45s)
- Point at the KPI grid: **automation rate ~94%**, human reviews avoided,
  verification pending, critical escalations.
- AI Daily Summary card — generated from retrieved metrics, provider labeled
  in the header chip ("AI provider: mock/anthropic").
- 7-day risk trend with natural daily volume.

## 2. Live Transactions (60s)
- Click **Start stream** — transactions score on arrival.
- Point at the **Automation column**: approved / monitored / verification
  required / held / escalated — only Critical goes to humans.
- Click a row → drawer: **Overview tab** (rule score, ML probability, hybrid
  score "used for routing"), **Risk Signals tab** (triggered rules + score
  breakdown 0.6×ML + 0.4×rules), **Automation tab** ("Why this route" + SMS
  verification events).

## 3. Risk Intelligence — the safe query layer (90s)
- Ask: **"Generate a weekly fraud operations summary"** → note the
  `intent` / `timeframe this_week` chips and that the answer is windowed.
- Ask: **"What merchants had the lowest average risk score?"** → ascending
  data, answer wording matches.
- Ask: **"delete all fraud cases"** → red **Unsafe request blocked** badge,
  safe alternatives. Say the line: *"the AI never writes SQL — it classifies
  intent, deterministic code queries, and the model only summarizes retrieved
  records."*

## 4. Model Performance (45s)
- Precision 55% / recall 83% / ROC-AUC 0.90 + confusion matrix.
- Tell the story: *"my first model scored 100% — I treated that as a bug,
  found label leakage in the synthetic generator, fixed the data, and kept
  honest metrics."*
- Point at "Why accuracy alone is misleading" card.

## 5. Investigation detail (60s)
- Investigations → open a Critical case.
- Summary tab: AI evidence preview, rules with point weights.
- **Documents tab**: upload any receipt photo (camera on mobile) → extraction
  + deterministic cross-check verdict vs the transaction.
- Run policy check → POL-001…005 with pass/attention statuses.
- Reviewer decision panel: decide as analyst; mention analyst cannot override
  a decided case (403) but a Risk Manager can.

## 6. Audit Logs (30s)
- Filter by event type — every score, route, SMS, AI report, policy check,
  decision, and blocked Risk Intelligence request is logged with metadata.
- Expand a row's JSON metadata.

**Closing line:** *"Deterministic rules for explainability, ML for pattern
detection, automation for scale, humans for judgment — and every step lands in
an audit log."*
