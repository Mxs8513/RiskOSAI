/**
 * Seeded, fully client-side demo data for RiskOS AI.
 *
 * Purpose: keep the console fully usable for a recruiter even when the backend
 * is cold-starting (Render free tier) or unreachable. None of this represents
 * real activity — it mirrors the *shape* of the live API responses so the same
 * components render whether data comes from the API or this fallback.
 *
 * This module is pure data + a resolver. It must NOT import from api.ts to avoid
 * a circular dependency.
 */

const now = Date.now();
const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

// ----------------------------------------------------------------------------
// Demo accounts (mirror /auth/demo-users — never includes passwords)
// ----------------------------------------------------------------------------
export const DEMO_USERS_PUBLIC = [
  { email: "analyst@northstar.demo", name: "Avery Chen", role: "fraud_analyst" },
  { email: "manager@northstar.demo", name: "Jordan Reyes", role: "risk_manager" },
  { email: "developer@northstar.demo", name: "Sam Okafor", role: "developer" },
  { email: "admin@northstar.demo", name: "Riley Park", role: "admin" },
];

// ----------------------------------------------------------------------------
// /health
// ----------------------------------------------------------------------------
const HEALTH = {
  status: "ok",
  environment: "Demo (seeded data)",
  org: "Northstar Financial",
  ai_provider: "anthropic",
  sms: {
    sms_enabled: false,
    twilio_configured: false,
    from_number_present: false,
    demo_phone_present: false,
    provider: "disabled",
  },
};

// ----------------------------------------------------------------------------
// /metrics/overview
// ----------------------------------------------------------------------------
const OVERVIEW = {
  transactions_processed: 48213,
  flagged_alerts: 1284,
  open_cases: 37,
  critical_cases: 12,
  confirmed_fraud: 89,
  reviewer_agreement_rate: 0.912,
  false_positive_rate: 0.181,
  avg_review_seconds: 96,
  most_triggered_rule: "High-risk merchant category",
  automation_rate: 0.763,
  human_review_avoided: 41207,
  verification_required: 612,
  held_transactions: 24,
  critical_escalations: 18,
};

// ----------------------------------------------------------------------------
// /metrics/charts
// ----------------------------------------------------------------------------
const fmtDay = (msAgo: number) =>
  new Date(now - msAgo).toLocaleDateString("en-US", { month: "short", day: "numeric" });

const CHARTS = {
  daily_trend: [
    { date: fmtDay(6 * DAY), flagged: 168, critical: 9, confirmed: 11 },
    { date: fmtDay(5 * DAY), flagged: 182, critical: 12, confirmed: 13 },
    { date: fmtDay(4 * DAY), flagged: 155, critical: 7, confirmed: 9 },
    { date: fmtDay(3 * DAY), flagged: 201, critical: 14, confirmed: 16 },
    { date: fmtDay(2 * DAY), flagged: 176, critical: 10, confirmed: 12 },
    { date: fmtDay(1 * DAY), flagged: 194, critical: 13, confirmed: 15 },
    { date: fmtDay(0), flagged: 188, critical: 12, confirmed: 13 },
  ],
  score_distribution: [
    { bucket: "0-9", count: 18240 }, { bucket: "10-19", count: 12110 },
    { bucket: "20-29", count: 7320 }, { bucket: "30-39", count: 4180 },
    { bucket: "40-49", count: 2510 }, { bucket: "50-59", count: 1490 },
    { bucket: "60-69", count: 820 }, { bucket: "70-79", count: 410 },
    { bucket: "80-89", count: 196 }, { bucket: "90-100", count: 88 },
  ],
  reviewer_outcomes: [
    { outcome: "true_positive", count: 89 },
    { outcome: "false_positive", count: 41 },
    { outcome: "pending", count: 37 },
  ],
  top_risk_merchants: [
    { name: "Crypto-X Exchange", avg_risk_score: 74, transactions: 312 },
    { name: "QuickCash ATM #221", avg_risk_score: 68, transactions: 188 },
    { name: "LuxeWatch Online", avg_risk_score: 61, transactions: 142 },
    { name: "GameKeys Store", avg_risk_score: 55, transactions: 207 },
    { name: "TravelFare Intl", avg_risk_score: 49, transactions: 96 },
  ],
};

// ----------------------------------------------------------------------------
// /metrics/daily-summary
// ----------------------------------------------------------------------------
const DAILY_SUMMARY = {
  summary:
    "Flagged volume is steady week-over-week with a mild uptick in critical cases mid-week, driven mostly " +
    "by the high-risk merchant-category rule. Reviewer agreement remains strong at ~91%, and the false-positive " +
    "rate held near 18%. No anomalous spikes detected in the synthetic stream.",
  provider: "demo",
};

// ----------------------------------------------------------------------------
// /rules  and  /metrics/rules
// ----------------------------------------------------------------------------
const RULES = [
  { id: 1, rule_code: "R-MERCH-CAT", name: "High-risk merchant category", description: "Flags transactions to merchant categories with elevated historical fraud.", threshold: 0.6, weight: 0.22, status: "active", updated_at: iso(3 * DAY), trigger_count: 412, false_positives: 71, true_positives: 341, false_positive_rate: 0.172 },
  { id: 2, rule_code: "R-VELOCITY", name: "Transaction velocity spike", description: "Detects an unusual burst of transactions in a short window.", threshold: 5, weight: 0.18, status: "active", updated_at: iso(5 * DAY), trigger_count: 308, false_positives: 58, true_positives: 250, false_positive_rate: 0.188 },
  { id: 3, rule_code: "R-NEW-DEVICE", name: "New device + high amount", description: "High-value purchase from a device never seen for this customer.", threshold: 0.5, weight: 0.2, status: "active", updated_at: iso(2 * DAY), trigger_count: 276, false_positives: 49, true_positives: 227, false_positive_rate: 0.178 },
  { id: 4, rule_code: "R-GEO-DIST", name: "Impossible travel distance", description: "Geographic distance from prior transaction exceeds plausible travel.", threshold: 500, weight: 0.16, status: "active", updated_at: iso(8 * DAY), trigger_count: 197, false_positives: 31, true_positives: 166, false_positive_rate: 0.157 },
  { id: 5, rule_code: "R-AMOUNT-Z", name: "Amount anomaly (z-score)", description: "Transaction amount is a statistical outlier for this customer.", threshold: 3, weight: 0.14, status: "active", updated_at: iso(6 * DAY), trigger_count: 164, false_positives: 38, true_positives: 126, false_positive_rate: 0.232 },
  { id: 6, rule_code: "R-NIGHT-INTL", name: "Off-hours international", description: "International transaction during the customer's overnight hours.", threshold: 0.4, weight: 0.1, status: "inactive", updated_at: iso(12 * DAY), trigger_count: 88, false_positives: 22, true_positives: 66, false_positive_rate: 0.25 },
  { id: 7, rule_code: "R-CARD-TEST", name: "Card-testing pattern", description: "Sequence of small authorizations consistent with card testing.", threshold: 3, weight: 0.19, status: "active", updated_at: iso(1 * DAY), trigger_count: 142, false_positives: 17, true_positives: 125, false_positive_rate: 0.12 },
];

// ----------------------------------------------------------------------------
// /transactions
// ----------------------------------------------------------------------------
const mkTxn = (o: Partial<any> & { transaction_id: string }) => ({
  timestamp: iso(2 * HOUR),
  customer_id: "CUST_00481",
  merchant: "Generic Merchant",
  merchant_category: "retail",
  amount: 120.0,
  currency: "USD",
  city: "Austin",
  state: "TX",
  device_id: "DV_4471",
  transaction_type: "card_present",
  is_new_device: false,
  velocity_10_min: 1,
  distance_from_home_miles: 3.2,
  merchant_risk_score: 0.21,
  dataset_label: "synthetic",
  status: "cleared",
  rule_score: 18,
  ml_fraud_probability: 0.08,
  hybrid_score: 22,
  model_rule_agreement: true,
  routing_score_basis: "hybrid",
  automation_decision: "auto_cleared",
  verification_status: "not_required",
  human_review_required: false,
  hold_status: "none",
  escalation_reason: null,
  risk_score: 22,
  risk_level: "Low",
  recommended_action: "clear",
  rules_triggered: [],
  ...o,
});

const TRANSACTIONS = [
  mkTxn({ transaction_id: "TXN_90412", merchant: "QuickCash ATM #221", merchant_category: "atm", amount: 980.0, city: "Miami", state: "FL", is_new_device: true, velocity_10_min: 6, distance_from_home_miles: 1180, merchant_risk_score: 0.82, status: "flagged", rule_score: 78, ml_fraud_probability: 0.74, hybrid_score: 81, model_rule_agreement: true, automation_decision: "escalated", verification_status: "required", human_review_required: true, hold_status: "held", escalation_reason: "Impossible travel + new device", risk_score: 81, risk_level: "Critical", recommended_action: "block", rules_triggered: ["R-GEO-DIST", "R-NEW-DEVICE"] }),
  mkTxn({ transaction_id: "TXN_90418", merchant: "LuxeWatch Online", merchant_category: "jewelry", amount: 2450.0, city: "Newark", state: "NJ", is_new_device: true, velocity_10_min: 2, merchant_risk_score: 0.69, status: "flagged", rule_score: 64, ml_fraud_probability: 0.58, hybrid_score: 67, automation_decision: "escalated", verification_status: "required", human_review_required: true, risk_score: 67, risk_level: "High", recommended_action: "verify", rules_triggered: ["R-MERCH-CAT", "R-NEW-DEVICE"] }),
  mkTxn({ transaction_id: "TXN_90423", merchant: "CoffeeBar", merchant_category: "dining", amount: 7.25, status: "cleared", risk_score: 9, risk_level: "Low", recommended_action: "clear" }),
  mkTxn({ transaction_id: "TXN_90431", merchant: "GameKeys Store", merchant_category: "digital_goods", amount: 1.0, velocity_10_min: 9, merchant_risk_score: 0.6, status: "flagged", rule_score: 55, ml_fraud_probability: 0.49, hybrid_score: 57, automation_decision: "verification", verification_status: "required", human_review_required: true, risk_score: 57, risk_level: "High", recommended_action: "verify", rules_triggered: ["R-CARD-TEST", "R-VELOCITY"] }),
  mkTxn({ transaction_id: "TXN_90437", merchant: "Northwind Grocery", merchant_category: "grocery", amount: 86.4, status: "cleared", risk_score: 14, risk_level: "Low", recommended_action: "clear" }),
  mkTxn({ transaction_id: "TXN_90444", merchant: "TravelFare Intl", merchant_category: "travel", amount: 1320.0, city: "London", state: "—", transaction_type: "card_not_present", merchant_risk_score: 0.55, status: "flagged", rule_score: 49, ml_fraud_probability: 0.41, hybrid_score: 52, automation_decision: "verification", verification_status: "required", human_review_required: true, risk_score: 52, risk_level: "Medium", recommended_action: "verify", rules_triggered: ["R-NIGHT-INTL", "R-AMOUNT-Z"] }),
  mkTxn({ transaction_id: "TXN_90455", merchant: "City Pharmacy", merchant_category: "health", amount: 42.1, status: "cleared", risk_score: 11, risk_level: "Low", recommended_action: "clear" }),
  mkTxn({ transaction_id: "TXN_90460", merchant: "ElectroMart", merchant_category: "electronics", amount: 899.99, is_new_device: true, merchant_risk_score: 0.47, status: "flagged", rule_score: 44, ml_fraud_probability: 0.39, hybrid_score: 47, automation_decision: "verification", verification_status: "required", human_review_required: true, risk_score: 47, risk_level: "Medium", recommended_action: "verify", rules_triggered: ["R-NEW-DEVICE", "R-AMOUNT-Z"] }),
];

// ----------------------------------------------------------------------------
// /investigations  (list)
// ----------------------------------------------------------------------------
const mkInv = (o: Partial<any> & { investigation_id: string; transaction_id: string }) => ({
  customer_id: "CUST_00481",
  merchant: "Generic Merchant",
  amount: 500.0,
  risk_score: 60,
  risk_level: "High",
  status: "Open",
  recommended_action: "verify",
  policy_check_status: "pending",
  assigned_to: null,
  has_ai_report: false,
  decision: null,
  created_at: iso(3 * HOUR),
  ...o,
});

const INVESTIGATIONS = [
  mkInv({ investigation_id: "INV_5012", transaction_id: "TXN_90412", merchant: "QuickCash ATM #221", amount: 980.0, risk_score: 81, risk_level: "Critical", status: "Open", recommended_action: "block", policy_check_status: "attention", has_ai_report: true, created_at: iso(35 * MIN) }),
  mkInv({ investigation_id: "INV_5013", transaction_id: "TXN_90418", merchant: "LuxeWatch Online", amount: 2450.0, risk_score: 67, risk_level: "High", status: "Hold for Review", recommended_action: "verify", assigned_to: "Avery Chen", created_at: iso(1 * HOUR) }),
  mkInv({ investigation_id: "INV_5014", transaction_id: "TXN_90431", merchant: "GameKeys Store", amount: 1.0, risk_score: 57, risk_level: "High", status: "Open", recommended_action: "verify", created_at: iso(2 * HOUR) }),
  mkInv({ investigation_id: "INV_5015", transaction_id: "TXN_90444", merchant: "TravelFare Intl", amount: 1320.0, risk_score: 52, risk_level: "Medium", status: "Open", recommended_action: "verify", created_at: iso(3 * HOUR) }),
  mkInv({ investigation_id: "INV_5016", transaction_id: "TXN_90460", merchant: "ElectroMart", amount: 899.99, risk_score: 47, risk_level: "Medium", status: "Hold for Review", recommended_action: "verify", assigned_to: "Jordan Reyes", created_at: iso(5 * HOUR) }),
  mkInv({ investigation_id: "INV_5009", transaction_id: "TXN_90388", merchant: "Crypto-X Exchange", amount: 3100.0, risk_score: 88, risk_level: "Critical", status: "Confirmed Fraud", recommended_action: "block", policy_check_status: "pass", has_ai_report: true, decision: "confirm_fraud", created_at: iso(1 * DAY) }),
  mkInv({ investigation_id: "INV_5007", transaction_id: "TXN_90377", merchant: "Boutique Hotel", amount: 640.0, risk_score: 39, risk_level: "Medium", status: "Cleared", recommended_action: "clear", policy_check_status: "pass", decision: "legitimate", created_at: iso(1 * DAY + 4 * HOUR) }),
  mkInv({ investigation_id: "INV_5003", transaction_id: "TXN_90341", merchant: "QuickCash ATM #118", amount: 1500.0, risk_score: 84, risk_level: "Critical", status: "Confirmed Fraud", recommended_action: "block", decision: "confirm_fraud", created_at: iso(2 * DAY) }),
];

// ----------------------------------------------------------------------------
// /investigations/:id  (detail)  — a single rich, self-consistent case
// ----------------------------------------------------------------------------
const INVESTIGATION_DETAIL = (id: string) => {
  const base = INVESTIGATIONS.find((i) => i.investigation_id === id) || INVESTIGATIONS[0];
  const txn = TRANSACTIONS.find((t) => t.transaction_id === base.transaction_id) || TRANSACTIONS[0];
  return {
    ...base,
    transaction: txn,
    rules_triggered: [
      { code: "R-GEO-DIST", name: "Impossible travel distance", points: 42, detail: "1,180 miles since prior transaction" },
      { code: "R-NEW-DEVICE", name: "New device + high amount", points: 36, detail: "First appearance of device DV_4471" },
    ],
    policies: [
      { code: "POL-01", title: "Step-up verification on critical risk", text: "Transactions scored Critical must receive customer verification before settlement." },
      { code: "POL-02", title: "Dual review on confirmed fraud", text: "A confirmed-fraud disposition on amounts over $1,000 requires a manager override." },
    ],
    ai_report: base.has_ai_report
      ? {
          generated_by: "anthropic",
          created_at: iso(20 * MIN),
          risk_summary:
            "This transaction combines a never-before-seen device with a geographic distance inconsistent with the " +
            "customer's recent activity, at an ATM merchant category that carries elevated fraud history.",
          evidence_bullets: [
            "New device (DV_4471) — first appearance for CUST_00481.",
            "Distance from home of 1,180 miles exceeds plausible travel since the prior transaction.",
            "Merchant category 'atm' has an above-baseline historical fraud rate.",
            "Rule and ML signals agree (hybrid score 81), reducing the chance of a false positive.",
          ],
          rules_explanation:
            "Triggered R-GEO-DIST (impossible travel) and R-NEW-DEVICE (new device + high amount). Combined weighting " +
            "pushed the hybrid score into the Critical band.",
          comparable_pattern:
            "Pattern resembles prior confirmed cases where a new device is paired with a high-value ATM withdrawal far from home.",
          recommended_action: "block",
          customer_impact_note:
            "If legitimate, the customer would be briefly inconvenienced by a verification step; given the signal strength, blocking pending verification is appropriate.",
          reviewer_checklist: [
            "Confirm whether the customer recently traveled to the transaction city.",
            "Check for a registered device change in the last 24 hours.",
            "Verify no prior chargebacks on this merchant for this customer.",
          ],
          audit_note: "AI evidence packet generated from structured risk-engine signals only. Not a decision; advisory to the human reviewer.",
        }
      : null,
    policy_check:
      base.policy_check_status && base.policy_check_status !== "pending"
        ? {
            created_at: iso(15 * MIN),
            policy_status: base.policy_check_status === "pass" ? "pass" : "attention",
            explanation:
              base.policy_check_status === "pass"
                ? "All applicable fraud policies were satisfied for this case."
                : "This case requires step-up verification under POL-01 before any settlement.",
            issues:
              base.policy_check_status === "pass"
                ? []
                : ["Critical risk score without a completed verification step."],
            policies_checked: [
              { code: "POL-01", status: base.policy_check_status === "pass" ? "pass" : "attention", note: "Step-up verification on critical risk" },
              { code: "POL-02", status: "pass", note: "Dual review on confirmed fraud" },
            ],
          }
        : null,
    reviewer_decision:
      base.decision
        ? {
            decision: base.decision,
            outcome: base.decision === "confirm_fraud" ? "true_positive" : "false_positive",
            reviewer: "Jordan Reyes",
            created_at: iso(10 * MIN),
            review_time_seconds: 84,
            ai_agreed: true,
            note: base.decision === "confirm_fraud" ? "Signals consistent with confirmed fraud; blocked and reported." : "Verified with customer; legitimate.",
          }
        : null,
    timeline: [
      { timestamp: base.created_at, actor: "system", event_type: "investigation_opened", message: `Case opened from flagged transaction ${base.transaction_id}.` },
      { timestamp: iso(25 * MIN), actor: "system", event_type: "risk_scored", message: `Hybrid risk score ${base.risk_score} (${base.risk_level}).` },
      { timestamp: iso(20 * MIN), actor: "anthropic", event_type: "ai_report_generated", message: "AI evidence packet generated from risk-engine signals." },
    ],
  };
};

// ----------------------------------------------------------------------------
// /notifications
// ----------------------------------------------------------------------------
const NOTIFICATIONS = [
  { id: 1, transaction_id: "TXN_90412", investigation_id: "INV_5012", channel: "sms", provider: "demo", to_phone_masked: "+1 (•••) •••-4471", message_body: "Northstar Financial: we paused a $980.00 ATM transaction in Miami, FL for your review. Reply YES if this was you.", status: "delivered", provider_message_id: "demo_msg_1001", sent_at: iso(33 * MIN), metadata: { simulated: true }, created_at: iso(33 * MIN) },
  { id: 2, transaction_id: "TXN_90418", investigation_id: "INV_5013", channel: "sms", provider: "demo", to_phone_masked: "+1 (•••) •••-2210", message_body: "Northstar Financial: please verify a $2,450.00 purchase at LuxeWatch Online.", status: "delivered", provider_message_id: "demo_msg_1002", sent_at: iso(58 * MIN), metadata: { simulated: true }, created_at: iso(58 * MIN) },
  { id: 3, transaction_id: "TXN_90431", investigation_id: "INV_5014", channel: "sms", provider: "demo", to_phone_masked: "+1 (•••) •••-7781", message_body: "Northstar Financial: unusual activity detected on your card. Was this you?", status: "queued", provider_message_id: null, sent_at: null, metadata: { simulated: true }, created_at: iso(2 * HOUR) },
  { id: 4, transaction_id: "TXN_90444", investigation_id: "INV_5015", channel: "sms", provider: "demo", to_phone_masked: "+1 (•••) •••-3390", message_body: "Northstar Financial: please confirm a $1,320.00 international transaction.", status: "delivered", provider_message_id: "demo_msg_1004", sent_at: iso(3 * HOUR), metadata: { simulated: true }, created_at: iso(3 * HOUR) },
];

// ----------------------------------------------------------------------------
// /audit
// ----------------------------------------------------------------------------
const AUDIT = [
  { id: 9001, timestamp: iso(10 * MIN), event_type: "reviewer_decision_submitted", actor: "Jordan Reyes", actor_role: "risk_manager", transaction_id: "TXN_90388", investigation_id: "INV_5009", message: "Jordan Reyes confirmed fraud on INV_5009", metadata: { outcome: "true_positive" } },
  { id: 9000, timestamp: iso(20 * MIN), event_type: "ai_report_generated", actor: "system", actor_role: "system", transaction_id: "TXN_90412", investigation_id: "INV_5012", message: "AI evidence packet generated for INV_5012", metadata: { provider: "anthropic" } },
  { id: 8999, timestamp: iso(33 * MIN), event_type: "notification_sent", actor: "system", actor_role: "system", transaction_id: "TXN_90412", investigation_id: "INV_5012", message: "Verification SMS sent (simulated) for INV_5012", metadata: { channel: "sms" } },
  { id: 8998, timestamp: iso(35 * MIN), event_type: "investigation_opened", actor: "system", actor_role: "system", transaction_id: "TXN_90412", investigation_id: "INV_5012", message: "Investigation INV_5012 opened from flagged transaction", metadata: {} },
  { id: 8997, timestamp: iso(1 * HOUR), event_type: "rule_triggered", actor: "system", actor_role: "system", transaction_id: "TXN_90412", investigation_id: null, message: "R-GEO-DIST triggered on TXN_90412", metadata: { rule_code: "R-GEO-DIST" } },
];

// ----------------------------------------------------------------------------
// /metrics/model  (Model Performance page)
// ----------------------------------------------------------------------------
const MODEL_PERF = {
  available: true,
  metadata: {
    model_name: "gradient_boosted_trees",
    trained_at: iso(2 * DAY),
    dataset: { n_samples: 84000, source: "PaySim-shaped synthetic", fraud_rate: 0.013, train_test_split: "75/25 stratified", class_imbalance_handling: "class weights + threshold tuning" },
    metrics: { accuracy: 0.987, precision: 0.829, recall: 0.741, f1: 0.783, roc_auc: 0.961, confusion_matrix: [[20612, 188], [241, 689]] },
  },
  live: {
    transactions_scored_by_ml: 48213,
    avg_rule_score: 21.4,
    avg_ml_probability: 0.114,
    avg_hybrid_score: 24.8,
    agreement_distribution: { high: 41080, medium: 5402, low: 1731 },
  },
};

// ----------------------------------------------------------------------------
// /risk-intelligence
// ----------------------------------------------------------------------------
const RISK_INTEL_SUGGESTIONS = [
  "Why was transaction TXN_90412 flagged?",
  "Which critical cases are still open?",
  "Generate a weekly fraud operations summary",
  "Which merchants had the lowest average risk score?",
  "How many transactions were automated this week?",
  "Show notification failures",
];

function riskIntelAnswer(question: string) {
  const q = (question || "").toLowerCase();
  if (q.includes("weekly") || q.includes("summary") || q.includes("operations")) {
    return {
      intent: "operations_summary",
      params: { timeframe: "this_week" },
      confidence: "high",
      blocked: false,
      answer:
        "**Weekly fraud operations summary** — 48,213 transactions processed, 1,284 flagged (2.7%). " +
        "12 critical cases, 89 confirmed fraud, false-positive rate ~18%. 76% of decisions were automated, " +
        "with reviewer agreement near 91%. The high-risk merchant-category rule drove the most flags.",
      sources: [{ type: "metrics", id: "overview" }],
      records: [OVERVIEW],
      provider: "anthropic",
    };
  }
  if (q.includes("merchant")) {
    const recs = RULES.slice(0, 3).map((r) => ({ name: r.name, avg_risk_score: Math.round(r.false_positive_rate * 100) }));
    return { intent: "merchant_risk_ranking", params: { direction: q.includes("lowest") || q.includes("safest") ? "asc" : "desc" }, confidence: "high", blocked: false,
      answer: "Ranked merchants by average risk score over the current window. See the records below for the ordered list.", sources: recs.map((r) => ({ type: "rule", id: r.name })), records: recs, provider: "anthropic" };
  }
  if (q.includes("delete") || q.includes("drop") || q.includes("password") || q.includes("secret") || q.includes("update ") || q.includes("ignore ")) {
    return { intent: "blocked", params: {}, confidence: "high", blocked: true,
      answer: "That request was blocked. Risk Intelligence only answers read-only analytical questions about fraud operations — it can't modify data, run destructive actions, or reveal secrets.",
      alternatives: RISK_INTEL_SUGGESTIONS.slice(0, 3), sources: [], records: [], provider: "anthropic" };
  }
  // transaction lookup / open cases / fallback
  return {
    intent: "case_lookup",
    params: {},
    confidence: "high",
    blocked: false,
    answer:
      "Based on the seeded window, the highest-risk open items are INV_5012 (QuickCash ATM, Critical, hybrid 81) and " +
      "INV_5013 (LuxeWatch Online, High, hybrid 67). Both combine a new device with elevated merchant-category risk.",
    sources: [{ type: "investigation", id: "INV_5012" }, { type: "investigation", id: "INV_5013" }],
    records: INVESTIGATIONS.slice(0, 3),
    provider: "anthropic",
  };
}

// ----------------------------------------------------------------------------
// /developer
// ----------------------------------------------------------------------------
const SAMPLE_PAYLOADS = {
  "POST /transactions/generate-batch?count=3": { count: 3 },
  "POST /investigations/{id}/review": { decision: "confirm_fraud", note: "Verified with customer" },
  "POST /risk-intelligence/query": { question: "Generate a weekly fraud operations summary" },
};

const SCENARIO_HISTORY = [
  { id: 1, rule_code: "R-GEO-DIST", expected: "flag", actual: "flag", passed: true, created_at: iso(1 * HOUR), payload: { amount: 980, distance_from_home_miles: 1180, is_new_device: true } },
  { id: 2, rule_code: "R-VELOCITY", expected: "flag", actual: "flag", passed: true, created_at: iso(3 * HOUR), payload: { velocity_10_min: 9, amount: 1 } },
  { id: 3, rule_code: "R-AMOUNT-Z", expected: "clear", actual: "flag", passed: false, created_at: iso(6 * HOUR), payload: { amount: 240, z_score: 2.1 } },
];

function runScenarioResult() {
  // Mirrors the backend score_transaction() shape the developer page reads.
  return {
    score: 81, risk_level: "Critical", recommended_action: "block", suggested_status: "Escalated",
    rules_triggered: [
      { code: "R-GEO-DIST", name: "Impossible travel distance", points: 42, detail: "1,180 miles since prior transaction" },
      { code: "R-NEW-DEVICE", name: "New device + high amount", points: 36, detail: "First appearance of device DV_4471" },
    ],
  };
}

function generateScenarioResult(ruleCode: string) {
  const code = ruleCode || "R-GEO-DIST";
  return {
    rule_code: code,
    scenarios: [
      { name: "Boundary: just over threshold", payload: { distance_from_home_miles: 505, is_new_device: true }, expected: "flag", actual: "flag", passed: true, rules_triggered: [code] },
      { name: "Boundary: just under threshold", payload: { distance_from_home_miles: 495, is_new_device: false }, expected: "clear", actual: "clear", passed: true, rules_triggered: [] },
      { name: "Compounding signals", payload: { distance_from_home_miles: 1180, velocity_10_min: 6 }, expected: "flag", actual: "flag", passed: true, rules_triggered: [code, "R-VELOCITY"] },
    ],
    summary: { total: 3, passed: 3, failed: 0 },
  };
}

// ----------------------------------------------------------------------------
// Resolver
// ----------------------------------------------------------------------------
function pathOnly(path: string) {
  return path.split("?")[0];
}

function queryParam(path: string, key: string): string | null {
  const q = path.split("?")[1];
  if (!q) return null;
  return new URLSearchParams(q).get(key);
}

/**
 * Map an API request to seeded demo data.
 *
 * Returns `undefined` when there is no sensible demo response for the path.
 * In "soft" callers (graceful fallback after a real request failed) this lets
 * the caller decide whether to surface the original error.
 */
export function demoResponse(path: string, opts: RequestInit = {}): unknown {
  const method = (opts.method || "GET").toUpperCase();
  const p = pathOnly(path);

  if (method === "GET") {
    if (p === "/health") return HEALTH;
    if (p === "/auth/demo-users") return DEMO_USERS_PUBLIC;
    if (p === "/auth/me") return null;
    if (p === "/metrics/overview") return OVERVIEW;
    if (p === "/metrics/charts") return CHARTS;
    if (p === "/metrics/rules") return RULES;
    if (p === "/metrics/daily-summary") return DAILY_SUMMARY;
    if (p === "/metrics/model") return MODEL_PERF;
    if (p === "/rules") return RULES;
    if (p === "/risk-intelligence/suggestions") return RISK_INTEL_SUGGESTIONS;
    if (p === "/developer/sample-payloads") return SAMPLE_PAYLOADS;
    if (p === "/developer/scenario-history") return SCENARIO_HISTORY;
    if (p === "/investigations") {
      const limit = Number(queryParam(path, "limit") || 0);
      return limit > 0 ? INVESTIGATIONS.slice(0, limit) : INVESTIGATIONS;
    }
    if (p.startsWith("/investigations/")) {
      const rest = p.slice("/investigations/".length);
      if (rest.endsWith("/evidence")) return [];
      return INVESTIGATION_DETAIL(rest);
    }
    if (p === "/transactions") return TRANSACTIONS;
    if (p.startsWith("/transactions/")) {
      const id = p.slice("/transactions/".length);
      return TRANSACTIONS.find((t) => t.transaction_id === id) || TRANSACTIONS[0];
    }
    if (p === "/notifications") {
      const txn = queryParam(path, "transaction_id");
      return txn ? NOTIFICATIONS.filter((n) => n.transaction_id === txn) : NOTIFICATIONS;
    }
    // Audit: backend route is /audit-logs and returns { limited_view, logs }.
    if (p === "/audit-logs" || p === "/audit") return { limited_view: false, logs: AUDIT };
    // Unknown GET — empty list is the safest shape for the list-heavy UI.
    return [];
  }

  // Mutations: acknowledge without changing anything (demo is read-only).
  if (p === "/auth/login") return { token: "demo-session", user: { id: 1, ...DEMO_USERS_PUBLIC[0], permissions: ["*"] } };
  if (p === "/transactions/generate-batch") {
    const count = Number(queryParam(path, "count") || 2);
    const generated = TRANSACTIONS.slice(0, Math.max(1, Math.min(count, TRANSACTIONS.length)));
    return { generated: generated.length, transactions: generated };
  }
  if (p === "/risk-intelligence/query") {
    let question = "";
    try { question = JSON.parse((opts.body as string) || "{}").question || ""; } catch { /* ignore */ }
    return riskIntelAnswer(question);
  }
  if (p === "/developer/generate-scenario") {
    let ruleCode = "";
    try { ruleCode = JSON.parse((opts.body as string) || "{}").rule_code || ""; } catch { /* ignore */ }
    return generateScenarioResult(ruleCode);
  }
  if (p === "/developer/run-scenario") return runScenarioResult();
  if (p.endsWith("/generate-ai-report")) return { provider: "anthropic" };
  if (p.endsWith("/policy-check")) return { status: "ok" };
  if (p.endsWith("/review")) return { outcome: "true_positive", ai_agreed: true };
  if (p.startsWith("/rules/")) return { status: "ok", rule_status: "active" };
  return { status: "ok" };
}

/** Whether the demo layer has a meaningful (non-empty) response for a path. */
export function hasDemoResponse(path: string, opts: RequestInit = {}): boolean {
  const method = (opts.method || "GET").toUpperCase();
  const p = pathOnly(path);
  if (method !== "GET") return true; // all mutations are acknowledged
  const known = [
    "/health", "/auth/demo-users", "/auth/me", "/metrics/overview", "/metrics/charts",
    "/metrics/rules", "/metrics/daily-summary", "/metrics/model", "/rules", "/investigations",
    "/transactions", "/notifications", "/audit", "/audit-logs",
    "/risk-intelligence/suggestions", "/developer/sample-payloads", "/developer/scenario-history",
  ];
  return known.includes(p) || p.startsWith("/investigations/") || p.startsWith("/transactions/");
}
