"use client";

import { useEffect, useState } from "react";
import { Brain } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Card, CardHeader, KV, Pill, Skeleton, StatCard } from "@/components/ui";
import { api, fmtPct, fmtTime } from "@/lib/api";

export default function ModelPerformancePage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api("/metrics/model").then(setData).catch(() => setData({ available: false }));
  }, []);

  if (!data) return <Shell><Skeleton rows={8} /></Shell>;

  const meta = data.metadata;
  const m = meta?.metrics;
  const cm = m?.confusion_matrix; // [[TN, FP], [FN, TP]]

  return (
    <Shell>
      <PageHeader
        title="Model Performance"
        subtitle="Optional ML fraud-scoring layer — the deterministic rule engine remains the explainability and audit layer"
      />

      {!data.available ? (
        <Card>
          <div className="p-8 text-center">
            <Brain className="mx-auto text-muted mb-2" size={22} />
            <p className="text-sm font-medium mb-1">No model trained yet</p>
            <p className="text-xs text-muted mb-3">
              Reach is running rules-only. Hybrid scoring activates automatically once a model artifact exists.
            </p>
            <p className="font-mono text-xs bg-bg border border-border rounded-lg px-3 py-2 inline-block">
              cd backend && python -m scripts.train_model
            </p>
          </div>
        </Card>
      ) : (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Accuracy" value={fmtPct(m?.accuracy)} sub="misleading alone — see below" />
            <StatCard label="Precision" value={fmtPct(m?.precision)} sub="flagged that were fraud" />
            <StatCard label="Recall" value={fmtPct(m?.recall)} sub="fraud that was caught" tone="success" />
            <StatCard label="F1" value={fmtPct(m?.f1)} sub="precision/recall balance" />
            <StatCard label="ROC-AUC" value={m?.roc_auc != null ? m.roc_auc.toFixed(3) : "—"} sub="ranking quality" tone="success" />
          </div>

          <div className="mb-5 grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader title="Model" subtitle="Trained offline by scripts/train_model.py" />
              <div className="divide-y divide-border">
                <KV k="Algorithm" v={<span className="font-medium capitalize">{(meta.model_name || "—").replace(/_/g, " ")}</span>} />
                <KV k="Trained" v={meta.trained_at ? fmtTime(meta.trained_at) : "—"} />
                <KV k="Dataset" v={meta.dataset?.n_samples != null
                  ? `${meta.dataset.n_samples.toLocaleString()} ${(meta.dataset.source || "").includes("PaySim") ? "PaySim-shaped" : ""} transactions`
                  : "—"} />
                <KV k="Fraud rate" v={fmtPct(meta.dataset?.fraud_rate)} />
                <KV k="Split" v={meta.dataset?.train_test_split || "75/25 stratified"} />
                <KV k="Imbalance handling" v={meta.dataset?.class_imbalance_handling || "class weights"} />
              </div>
            </Card>

            <Card>
              <CardHeader title="Confusion matrix" subtitle="Holdout set — rows: actual, columns: predicted" />
              {cm && (
                <div className="p-4">
                  <div className="grid grid-cols-[auto_1fr_1fr] gap-1 text-center text-xs">
                    <div />
                    <div className="py-1 font-medium text-muted">Pred. legit</div>
                    <div className="py-1 font-medium text-muted">Pred. fraud</div>
                    <div className="flex items-center pr-2 font-medium text-muted">Actual legit</div>
                    <div className="rounded-lg bg-success-soft py-4 ring-1 ring-inset ring-success-border">
                      <span className="font-mono text-base font-semibold text-success">{cm[0][0].toLocaleString()}</span>
                      <p className="text-[10px] text-muted">true negatives</p>
                    </div>
                    <div className="rounded-lg bg-warn-soft py-4 ring-1 ring-inset ring-warn-border">
                      <span className="font-mono text-base font-semibold text-warn">{cm[0][1].toLocaleString()}</span>
                      <p className="text-[10px] text-muted">false positives</p>
                    </div>
                    <div className="flex items-center pr-2 font-medium text-muted">Actual fraud</div>
                    <div className="rounded-lg bg-danger-soft py-4 ring-1 ring-inset ring-danger-border">
                      <span className="font-mono text-base font-semibold text-danger">{cm[1][0].toLocaleString()}</span>
                      <p className="text-[10px] text-muted">false negatives</p>
                    </div>
                    <div className="rounded-lg bg-success-soft py-4 ring-1 ring-inset ring-success-border">
                      <span className="font-mono text-base font-semibold text-success">{cm[1][1].toLocaleString()}</span>
                      <p className="text-[10px] text-muted">true positives</p>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            <Card>
              <CardHeader title="Rule score vs ML score" subtitle="Live comparison on the current transaction stream" />
              {data.live ? (
                <div className="divide-y divide-border">
                  <KV k="Transactions scored by ML" v={data.live.transactions_scored_by_ml.toLocaleString()} />
                  <KV k="Avg rule score" v={<span className="font-mono text-xs font-semibold">{data.live.avg_rule_score}/100</span>} />
                  <KV k="Avg ML probability" v={<span className="font-mono text-xs font-semibold">{(data.live.avg_ml_probability * 100).toFixed(1)}%</span>} />
                  <KV k="Avg hybrid score" v={<span className="font-mono text-xs font-semibold">{data.live.avg_hybrid_score}/100</span>} />
                  <KV k="Agreement" v={
                    <span className="flex gap-1.5">
                      {(["high", "medium", "low"] as const).map((k) => (
                        <span key={k} className="inline-flex items-center gap-1">
                          <Pill value={k} /> <span className="font-mono text-xs">{data.live.agreement_distribution[k]}</span>
                        </span>
                      ))}
                    </span>
                  } />
                </div>
              ) : (
                <p className="p-4 text-xs text-muted">No ML-scored transactions yet — reseed or generate a batch.</p>
              )}
            </Card>
          </div>

          <Card>
            <CardHeader title="Why accuracy alone is misleading for fraud detection" />
            <div className="space-y-2 px-4 pb-4 text-sm leading-relaxed text-muted">
              <p>
                Fraud is heavily imbalanced: only ~{meta.dataset ? Math.round(meta.dataset.fraud_rate * 100) : 12}% of
                transactions are fraudulent. A model that predicts <em>“legitimate”</em> for every single transaction
                would score ~{meta.dataset ? Math.round((1 - meta.dataset.fraud_rate) * 100) : 88}% accuracy while
                catching zero fraud.
              </p>
              <p>
                The metrics that matter are <span className="font-medium text-ink">precision</span> (how many flagged
                transactions were actually fraud — drives customer friction and analyst workload),{" "}
                <span className="font-medium text-ink">recall</span> (how much fraud was caught — drives losses),{" "}
                <span className="font-medium text-ink">F1</span> (their balance), and{" "}
                <span className="font-medium text-ink">ROC-AUC</span> (how well the model ranks risk across thresholds).
                This is also why Reach tracks the false-positive rate per rule and per reviewer decision.
              </p>
              <p>
                The ML model is never the final authority: the deterministic rules stay visible as the explainability
                layer, the hybrid score (0.6 × ML + 0.4 × rules) drives automated routing, and Critical cases always
                escalate to a human reviewer. This is a simulation — not production financial decisioning.
              </p>
            </div>
          </Card>
        </>
      )}
    </Shell>
  );
}
