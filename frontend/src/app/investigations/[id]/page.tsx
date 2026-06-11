"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Camera, CheckCircle2, FileText, ShieldAlert, Sparkles, XCircle } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, CardHeader, KV, Pill, RiskScore, Skeleton, Tabs, Toast } from "@/components/ui";
import { API_URL, api, can, fmtMoney, fmtTime, getToken } from "@/lib/api";

const TABS = ["Summary", "Evidence", "Documents", "Policy", "Audit"];

export default function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [inv, setInv] = useState<any>(null);
  const [tab, setTab] = useState("Summary");
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const openedAt = useRef(Date.now());

  const load = useCallback(async () => {
    try { setInv(await api(`/investigations/${id}`)); } catch (e: any) { setToast(e.message); }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2600);
  }

  async function generateReport() {
    setBusy("report");
    try {
      const res = await api<{ provider: string }>(`/investigations/${id}/generate-ai-report`, { method: "POST" });
      flash(`AI evidence packet generated (${res.provider})`);
      await load();
      setTab("Evidence");
    } catch (e: any) { flash(e.message); }
    setBusy(null);
  }

  async function runPolicyCheck() {
    setBusy("policy");
    try {
      await api(`/investigations/${id}/policy-check`, { method: "POST" });
      flash("Policy check completed");
      await load();
      setTab("Policy");
    } catch (e: any) { flash(e.message); }
    setBusy(null);
  }

  async function review(decision: string) {
    setBusy(decision);
    try {
      const res = await api<{ outcome: string; ai_agreed: boolean }>(`/investigations/${id}/review`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          note: note || null,
          review_time_seconds: Math.round((Date.now() - openedAt.current) / 1000),
        }),
      });
      flash(`Decision recorded — outcome: ${res.outcome.replace(/_/g, " ")} · AI ${res.ai_agreed ? "agreed" : "disagreed"}`);
      setNote("");
      await load();
    } catch (e: any) { flash(e.message); }
    setBusy(null);
  }

  if (!inv) return <Shell><Skeleton rows={10} /></Shell>;

  const t = inv.transaction;
  const decided = !!inv.reviewer_decision;
  const canReview = can("review");
  const canOverride = can("override");
  const reviewBlocked = !canReview || (decided && !canOverride);

  return (
    <Shell>
      <Link href="/investigations" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink mb-3">
        <ArrowLeft size={13} /> Back to investigations
      </Link>
      <PageHeader
        title={inv.investigation_id}
        subtitle={`Transaction ${inv.transaction_id} · created ${fmtTime(inv.created_at)}`}
        right={
          <div className="flex items-center gap-3">
            <RiskScore score={inv.risk_score} level={inv.risk_level} />
            <Pill value={inv.status} />
          </div>
        }
      />

      <div className="flex items-center gap-2 mb-4">
        <Button variant="primary" onClick={generateReport} disabled={busy === "report"}>
          <Sparkles size={14} /> {busy === "report" ? "Generating…" : inv.ai_report ? "Regenerate AI report" : "Generate AI report"}
        </Button>
        <Button onClick={runPolicyCheck} disabled={busy === "policy"}>
          <ShieldAlert size={14} /> {busy === "policy" ? "Checking…" : "Run policy check"}
        </Button>
      </div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      <div className="mt-4 grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {tab === "Summary" && (
            <>
              <Card>
                <CardHeader title="Transaction summary" />
                <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 divide-border">
                  <div className="divide-y divide-border">
                    <KV k="Amount" v={<span className="font-medium">{fmtMoney(t.amount)}</span>} />
                    <KV k="Customer" v={<span className="font-mono text-xs">{t.customer_id}</span>} />
                    <KV k="Merchant" v={`${t.merchant} (${t.merchant_category})`} />
                    <KV k="Location" v={`${t.city}, ${t.state}`} />
                    <KV k="Type" v={t.transaction_type?.replace(/_/g, " ")} />
                  </div>
                  <div className="divide-y divide-border">
                    <KV k="Device" v={<span className="font-mono text-xs">{t.device_id}{t.is_new_device ? " · new" : ""}</span>} />
                    <KV k="Velocity (10 min)" v={`${t.velocity_10_min} txns`} />
                    <KV k="Distance from home" v={`${Math.round(t.distance_from_home_miles)} mi`} />
                    <KV k="Merchant risk" v={t.merchant_risk_score?.toFixed(2)} />
                    <KV k="AI recommendation" v={<span className="capitalize font-medium">{inv.recommended_action}</span>} />
                  </div>
                </div>
              </Card>
              <Card>
                <CardHeader
                  title="AI evidence preview"
                  subtitle={inv.ai_report
                    ? `Provider: ${inv.ai_report.generated_by} · grounded in risk-engine signals only`
                    : "No AI evidence packet yet for this case"}
                  right={inv.ai_report && (
                    <button onClick={() => setTab("Evidence")} className="rounded-md text-xs font-medium text-primary hover:underline">
                      Full evidence →
                    </button>
                  )}
                />
                <div className="px-4 pb-4">
                  {inv.ai_report ? (
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {inv.ai_report.evidence_bullets.slice(0, 2).map((b: string, i: number) => <li key={i}>{b}</li>)}
                    </ul>
                  ) : (
                    <Button variant="primary" onClick={generateReport} disabled={busy === "report"}>
                      <Sparkles size={14} /> {busy === "report" ? "Generating…" : "Generate AI report"}
                    </Button>
                  )}
                </div>
              </Card>
              <Card>
                <CardHeader title="Rules triggered" subtitle="Deterministic risk-engine signals — not AI-generated" />
                <div className="px-4 pb-4 space-y-2">
                  {inv.rules_triggered.map((r: any) => (
                    <div key={r.code} className="flex items-start justify-between rounded-lg border border-border px-3 py-2">
                      <div>
                        <span className="font-mono text-xs text-muted mr-2">{r.code}</span>
                        <span className="text-sm font-medium">{r.name}</span>
                        <div className="text-xs text-muted mt-0.5">{r.detail}</div>
                      </div>
                      <span className="text-xs font-medium text-danger whitespace-nowrap">+{r.points}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {tab === "Evidence" && (
            !inv.ai_report ? (
              <Card>
                <div className="p-8 text-center">
                  <FileText className="mx-auto text-muted mb-2" size={22} />
                  <p className="text-sm text-muted mb-3">No AI evidence packet yet for this case.</p>
                  <Button variant="primary" onClick={generateReport} disabled={busy === "report"}>
                    <Sparkles size={14} /> Generate AI report
                  </Button>
                </div>
              </Card>
            ) : (
              <Card>
                <CardHeader
                  title="AI evidence packet"
                  subtitle={`Generated ${fmtTime(inv.ai_report.created_at)} · provider: ${inv.ai_report.generated_by} · references only structured risk-engine signals`}
                />
                <div className="px-4 pb-4 space-y-4 text-sm">
                  <Section label="Risk summary">{inv.ai_report.risk_summary}</Section>
                  <Section label="Top evidence">
                    <ul className="list-disc pl-5 space-y-1">
                      {inv.ai_report.evidence_bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}
                    </ul>
                  </Section>
                  <Section label="Rules explanation">{inv.ai_report.rules_explanation}</Section>
                  <Section label="Comparable pattern">{inv.ai_report.comparable_pattern}</Section>
                  <Section label="Recommended action"><span className="capitalize font-medium">{inv.ai_report.recommended_action}</span></Section>
                  <Section label="Customer impact note">{inv.ai_report.customer_impact_note}</Section>
                  <Section label="Reviewer checklist">
                    <ul className="space-y-1">
                      {inv.ai_report.reviewer_checklist.map((c: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-muted mt-0.5 shrink-0" /> {c}
                        </li>
                      ))}
                    </ul>
                  </Section>
                  <Section label="Audit-ready note">
                    <p className="bg-bg rounded-lg border border-border p-3 text-xs font-mono leading-relaxed">{inv.ai_report.audit_note}</p>
                  </Section>
                </div>
              </Card>
            )
          )}

          {tab === "Documents" && <DocumentsTab invId={inv.investigation_id} flash={flash} />}

          {tab === "Policy" && (
            <>
              {!inv.policy_check ? (
                <Card>
                  <div className="p-8 text-center">
                    <ShieldAlert className="mx-auto text-muted mb-2" size={22} />
                    <p className="text-sm text-muted mb-3">Policy compliance has not been checked for this case yet.</p>
                    <Button variant="primary" onClick={runPolicyCheck} disabled={busy === "policy"}>Run policy check</Button>
                  </div>
                </Card>
              ) : (
                <Card>
                  <CardHeader
                    title="Policy / compliance check"
                    subtitle={`Checked ${fmtTime(inv.policy_check.created_at)}`}
                    right={<Pill value={inv.policy_check.policy_status} />}
                  />
                  <div className="px-4 pb-4 space-y-3 text-sm">
                    <Section label="Explanation">{inv.policy_check.explanation}</Section>
                    {inv.policy_check.issues?.length > 0 && (
                      <Section label="Issues">
                        <ul className="list-disc pl-5 space-y-1 text-danger">
                          {inv.policy_check.issues.map((x: any, i: number) => (
                            <li key={i}>{typeof x === "string" ? x : `${x.code}: ${x.issue}`}</li>
                          ))}
                        </ul>
                      </Section>
                    )}
                    <Section label="Policies checked">
                      <div className="space-y-1.5">
                        {inv.policy_check.policies_checked.map((p: any, i: number) => (
                          <div key={p.code || i} className="flex items-start justify-between gap-3 rounded-lg border border-border px-3 py-2">
                            <div className="min-w-0">
                              <span className="font-mono text-xs text-muted mr-2">{typeof p === "string" ? p : p.code}</span>
                              {typeof p !== "string" && p.note && <span className="text-xs text-muted">{p.note}</span>}
                            </div>
                            {typeof p !== "string" && p.status && (
                              <Pill value={p.status === "pass" ? "Passed" : p.status === "attention" ? "Needs Review" : p.status} />
                            )}
                          </div>
                        ))}
                      </div>
                    </Section>
                  </div>
                </Card>
              )}
              <Card>
                <CardHeader title="Internal fraud policies" subtitle="Northstar Financial fraud operations policy set (simulated)" />
                <div className="px-4 pb-4 space-y-2">
                  {inv.policies.map((p: any) => (
                    <div key={p.code} className="rounded-lg border border-border px-3 py-2">
                      <span className="font-mono text-xs text-muted mr-2">{p.code}</span>
                      <span className="text-sm font-medium">{p.title}</span>
                      <p className="text-xs text-muted mt-0.5">{p.text}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {tab === "Audit" && (
            <Card>
              <CardHeader title="Audit timeline" subtitle="Every action on this case is logged" />
              <div className="px-4 pb-4">
                <ol className="relative border-l border-border ml-2 space-y-4 py-1">
                  {inv.timeline.map((e: any, i: number) => (
                    <li key={i} className="ml-4">
                      <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-primary/60 border-2 border-card" />
                      <div className="text-xs text-muted">{fmtTime(e.timestamp)} · {e.actor}</div>
                      <div className="text-sm">
                        <span className="font-mono text-xxs text-muted mr-2">{e.event_type}</span>
                        {e.message}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Reviewer decision" subtitle={decided ? "A decision has been recorded for this case" : "Human-in-the-loop disposition"} />
            <div className="px-4 pb-4">
              {inv.reviewer_decision && (
                <div className="rounded-lg border border-border p-3 mb-3 text-sm bg-bg">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium capitalize">{inv.reviewer_decision.decision.replace(/_/g, " ")}</span>
                    <Pill value={inv.reviewer_decision.outcome} />
                  </div>
                  <p className="text-xs text-muted">
                    {inv.reviewer_decision.reviewer} · {fmtTime(inv.reviewer_decision.created_at)} ·{" "}
                    {inv.reviewer_decision.review_time_seconds}s · AI {inv.reviewer_decision.ai_agreed ? "agreed" : "disagreed"}
                  </p>
                  {inv.reviewer_decision.note && <p className="text-xs mt-1.5">“{inv.reviewer_decision.note}”</p>}
                </div>
              )}
              <textarea
                className="w-full rounded-lg border border-border px-3 py-2 text-sm mb-3 shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-[border-color,box-shadow] duration-150 placeholder:text-faint hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary"
                rows={2}
                placeholder="Reviewer note (optional)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={reviewBlocked}
              />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="danger" disabled={reviewBlocked || !!busy} onClick={() => review("confirm_fraud")}>Confirm fraud</Button>
                <Button variant="success" disabled={reviewBlocked || !!busy} onClick={() => review("clear")}>Clear transaction</Button>
                <Button disabled={reviewBlocked || !!busy} onClick={() => review("step_up")}>Request step-up</Button>
                <Button disabled={reviewBlocked || !!busy} onClick={() => review("escalate")}>Escalate</Button>
              </div>
              {!canReview && <p className="text-xxs text-muted mt-2">Your role does not have review permission.</p>}
              {decided && canReview && !canOverride && (
                <p className="text-xxs text-muted mt-2">Case already decided — only a Risk Manager or Admin can override.</p>
              )}
              {decided && canOverride && (
                <p className="text-xxs text-warn mt-2">Submitting again will override the prior decision (logged to audit trail).</p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Case details" />
            <div className="divide-y divide-border">
              <KV k="Status" v={<Pill value={inv.status} />} />
              <KV k="Rule score" v={<span className="font-mono text-xs font-semibold">{inv.rule_score}/100</span>} />
              <KV k="ML fraud probability" v={inv.ml_fraud_probability != null
                ? <span className="font-mono text-xs font-semibold">{(inv.ml_fraud_probability * 100).toFixed(0)}%</span>
                : <span className="text-xs text-muted">model not trained</span>} />
              <KV k="Hybrid score" v={<span className="font-mono text-xs font-semibold">
                {inv.hybrid_score ?? inv.rule_score}/100
                <span className="ml-1.5 font-sans font-normal text-[10px] text-faint">
                  ({inv.routing_score_basis === "hybrid" ? "used for routing" : "rules only"})
                </span>
              </span>} />
              {inv.model_rule_agreement && <KV k="Model/rule agreement" v={<Pill value={inv.model_rule_agreement} />} />}
              <KV k="Policy check" v={inv.policy_check_status ? <Pill value={inv.policy_check_status} /> : "—"} />
              <KV k="Assigned to" v={inv.assigned_to || "Unassigned"} />
              <KV k="AI recommendation" v={<span className="capitalize">{inv.recommended_action}</span>} />
              <KV k="Transaction" v={<Link className="text-primary font-mono text-xs hover:underline" href={`/transactions?search=${inv.transaction_id}`}>{inv.transaction_id}</Link>} />
            </div>
          </Card>
        </div>
      </div>
      <Toast message={toast} />
    </Shell>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted uppercase tracking-wide mb-1">{label}</p>
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  );
}

/* ------------------------- Evidence Intake & Cross-Check ------------------------ */

function DocumentsTab({ invId, flash }: { invId: string; flash: (m: string) => void }) {
  const [docs, setDocs] = useState<any[] | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api(`/investigations/${invId}/evidence`).then(setDocs).catch(() => setDocs([]));
  }, [invId]);

  useEffect(() => { load(); }, [load]);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/investigations/${invId}/evidence`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form,
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Upload failed");
      flash(`Document analyzed — verdict: ${body.verdict.replace(/_/g, " ")}`);
      load();
    } catch (err: any) { flash(err.message); }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Submit document evidence"
          subtitle="Photograph or upload a receipt, ticket, bank letter, police report, or handwritten dispute letter. Extracted fields are cross-checked against the transaction record deterministically."
        />
        <div className="px-4 pb-4">
          <input ref={fileRef} type="file" accept="image/*" capture="environment"
            onChange={onFile} className="hidden" id="evidence-file" />
          <Button variant="primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <Camera size={14} /> {uploading ? "Analyzing…" : "Photo / upload document"}
          </Button>
          <p className="text-xxs text-faint mt-2">
            JPEG/PNG/WebP up to 8 MB. The vision model never sees the transaction — comparison is done in code.
          </p>
        </div>
      </Card>

      {!docs ? <Skeleton rows={4} /> : docs.length === 0 ? (
        <Card>
          <p className="p-6 text-center text-sm text-muted">No documents submitted for this case yet.</p>
        </Card>
      ) : docs.map((d) => (
        <Card key={d.id}>
          <CardHeader
            title={`${d.filename}`}
            subtitle={`${d.document_type.replace(/_/g, " ")} · uploaded by ${d.uploaded_by} · ${fmtTime(d.created_at)} · provider: ${d.provider}`}
            right={<Pill value={d.verdict} />}
          />
          <div className="px-4 pb-4 space-y-3 text-sm">
            {d.claim_summary && <Section label="Document claims">{d.claim_summary}</Section>}
            <Section label={`Cross-check vs ${d.transaction_id} · confidence ${(d.confidence * 100).toFixed(0)}%`}>
              <div className="space-y-1.5">
                {d.checks.map((c: any, i: number) => (
                  <div key={i} className="flex items-start justify-between rounded-lg border border-border px-3 py-2 text-xs">
                    <div>
                      <span className="font-medium capitalize mr-2">{c.field}</span>
                      <span className="text-muted">document: <span className="text-ink">{c.document_value}</span></span>
                      <span className="mx-1.5 text-faint">·</span>
                      <span className="text-muted">transaction: <span className="text-ink">{c.transaction_value}</span></span>
                    </div>
                    {c.match
                      ? <CheckCircle2 size={15} className="shrink-0 text-success" />
                      : <XCircle size={15} className="shrink-0 text-danger" />}
                  </div>
                ))}
                {d.checks.length === 0 && <p className="text-xs text-muted">No comparable fields could be read.</p>}
              </div>
            </Section>
            {d.extraction?.suspicious_artifacts?.length > 0 && (
              <Section label="Tampering signals">
                <ul className="list-disc pl-5 text-danger text-xs space-y-0.5">
                  {d.extraction.suspicious_artifacts.map((a: string, i: number) => <li key={i}>{a}</li>)}
                </ul>
              </Section>
            )}
            <EvidenceThumb id={d.id} filename={d.filename} />
          </div>
        </Card>
      ))}
    </>
  );
}

function EvidenceThumb({ id, filename }: { id: number; filename: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let objectUrl: string | null = null;
    fetch(`${API_URL}/evidence/${id}/file`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((b) => { objectUrl = URL.createObjectURL(b); setUrl(objectUrl); })
      .catch(() => {});
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id]);
  if (!url) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={filename} className="max-h-56 rounded-lg border border-border" />;
}
