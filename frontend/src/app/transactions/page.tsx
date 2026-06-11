"use client";

import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MessageSquare, Pause, Play, PlusCircle, RefreshCw } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, Drawer, Pill, RiskScore, Select, Skeleton, Table, Tabs, Toast } from "@/components/ui";
import { api, can, fmtMoney, fmtTime } from "@/lib/api";

const RISK_LEVELS = ["Low", "Medium", "High", "Critical"];
const STATUSES = ["Approved", "Monitoring", "Pending Verification", "Held for Verification", "Hold for Review", "Escalated", "Cleared", "Confirmed Fraud"];
const CATEGORIES = ["electronics", "travel", "jewelry", "grocery", "restaurants", "gas", "online_marketplace", "wire_transfer", "gift_cards", "pharmacy"];

function TransactionsInner() {
  const params = useSearchParams();
  const [rows, setRows] = useState<any[] | null>(null);
  const [riskLevel, setRiskLevel] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState(params.get("search") || "");
  const [streaming, setStreaming] = useState(false);
  const [selected, setSelected] = useState<any | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const qs = new URLSearchParams();
    if (riskLevel) qs.set("risk_level", riskLevel);
    if (status) qs.set("status", status);
    if (category) qs.set("merchant_category", category);
    if (search) qs.set("search", search);
    qs.set("limit", "80");
    try {
      setRows(await api(`/transactions?${qs.toString()}`));
    } catch { setRows([]); }
  }, [riskLevel, status, category, search]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (streaming) {
      timer.current = setInterval(async () => {
        try {
          const res = await api<{ transactions: any[] }>("/transactions/generate-batch?count=2", { method: "POST" });
          setNewIds(new Set(res.transactions.map((t) => t.transaction_id)));
          await load();
        } catch { /* ignore */ }
      }, 4000);
    }
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [streaming, load]);

  async function generateBatch() {
    try {
      const res = await api<{ generated: number; transactions: any[] }>("/transactions/generate-batch?count=5", { method: "POST" });
      setNewIds(new Set(res.transactions.map((t) => t.transaction_id)));
      setToast(`${res.generated} transactions processed through the risk engine`);
      setTimeout(() => setToast(null), 2500);
      await load();
    } catch (e: any) {
      setToast(e.message); setTimeout(() => setToast(null), 2500);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Live Transactions"
        subtitle="Simulated real-time transaction monitoring — every transaction is scored on arrival"
        right={
          <div className="flex items-center gap-2">
            <Button variant={streaming ? "secondary" : "primary"} onClick={() => setStreaming(!streaming)}>
              {streaming
                ? <><span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse-ring" aria-hidden /> Live <Pause size={13} /></>
                : <><Play size={13} /> Start stream</>}
            </Button>
            <Button onClick={generateBatch}><PlusCircle size={14} /> Generate batch</Button>
            <Button variant="ghost" onClick={load} title="Refresh"><RefreshCw size={14} /></Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          className="w-56 rounded-lg border border-border bg-card px-3 py-1.5 text-xs shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-[border-color,box-shadow] duration-150 placeholder:text-faint hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary"
          placeholder="Search txn / merchant / customer"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={riskLevel} onChange={setRiskLevel} options={RISK_LEVELS} placeholder="All risk levels" />
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
        <Select value={category} onChange={setCategory} options={CATEGORIES} placeholder="All categories" />
      </div>

      <Card>
        {!rows ? <div className="p-4"><Skeleton rows={8} /></div> : (
          <Table head={["Time", "Transaction", "Customer", "Merchant", "Amount", "Location", "Device", "Risk", "Automation", "Status", ""]} empty={rows.length === 0}>
            {rows.map((t) => (
              <tr
                key={t.transaction_id}
                onClick={() => setSelected(t)}
                className={`group cursor-pointer ${newIds.has(t.transaction_id) ? "bg-primary-soft/60" : ""}`}
              >
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[11px] text-faint">{fmtTime(t.timestamp)}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{t.transaction_id}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{t.customer_id}</td>
                <td className="px-4 py-2.5 text-[13px] font-medium">
                  {t.merchant}
                  <div className="text-[10px] font-normal text-faint">{t.merchant_category}</div>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{fmtMoney(t.amount)}</td>
                <td className="px-4 py-2.5 text-xs text-muted">{t.city}, {t.state}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">
                  {t.device_id}
                  {t.is_new_device && <span className="ml-1.5 rounded bg-warn-soft px-1 py-px text-[10px] font-medium text-warn ring-1 ring-inset ring-warn-border">new</span>}
                </td>
                <td className="px-4 py-2.5"><RiskScore score={t.risk_score} level={t.risk_level} /></td>
                <td className="px-4 py-2.5"><Pill value={t.automation_decision} /></td>
                <td className="px-4 py-2.5"><Pill value={t.status} /></td>
                <td className="px-4 py-2.5 text-xs font-medium text-primary opacity-0 transition-opacity duration-100 group-hover:opacity-100">View →</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selected?.transaction_id || ""}>
        {selected && <TxnDetail txn={selected} />}
      </Drawer>
      <Toast message={toast} />
    </Shell>
  );
}

function TxnDetail({ txn }: { txn: any }) {
  const [full, setFull] = useState<any>(txn);
  const [notifs, setNotifs] = useState<any[] | null>(null);
  const [sending, setSending] = useState(false);
  const [sendMsg, setSendMsg] = useState<string | null>(null);

  const loadNotifs = useCallback(() => {
    api(`/notifications?transaction_id=${txn.transaction_id}`).then(setNotifs).catch(() => setNotifs([]));
  }, [txn.transaction_id]);

  useEffect(() => {
    api(`/transactions/${txn.transaction_id}`).then(setFull).catch(() => {});
    loadNotifs();
  }, [txn.transaction_id, loadNotifs]);

  async function sendTestSms() {
    setSending(true);
    setSendMsg(null);
    try {
      const res = await api<{ status: string; metadata: any }>(
        `/notifications/send-verification/${txn.transaction_id}`, { method: "POST" });
      setSendMsg(res.status === "sent" ? "SMS sent" : `Queued (${res.metadata?.reason || "pending"})`);
      loadNotifs();
    } catch (e: any) { setSendMsg(e.message); }
    setSending(false);
  }

  const smsEligible = ["verification_required", "held_for_verification"].includes(full.automation_decision);
  const [tab, setTab] = useState("Overview");
  const dash = (v: any) => (v == null || v === "" ? "—" : v);

  const WHY: Record<string, string> = {
    approved: "Score landed in the Low tier (0–39) — approved automatically with zero customer friction.",
    monitored: "Score landed in the Medium tier (40–59) — approved, but kept under monitoring.",
    verification_required: "Score landed in the Elevated tier (60–74) — the customer is asked to verify; no human analyst needed yet.",
    held_for_verification: "Score landed in the High tier (75–84) — the transaction is held until the customer verifies; no human analyst needed yet.",
    escalated_to_human_review: full.escalation_reason || "Score landed in the Critical tier (85–100) — held and escalated to a human reviewer immediately.",
  };

  return (
    <div>
      {/* ----- header summary card ----- */}
      <div className="px-5 pb-4 pt-4">
        <div className="rounded-xl border border-border bg-bg p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-lg font-semibold tracking-[-0.01em]">{fmtMoney(full.amount)}</p>
              <p className="truncate text-xs text-muted">
                {dash(full.merchant)} · {full.timestamp ? fmtTime(full.timestamp) : "—"}
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1.5">
              <Pill value={full.status} />
              <Pill value={full.automation_decision} />
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
            <RiskScore score={full.hybrid_score ?? full.risk_score} level={full.risk_level} />
            <span className="text-[10px] text-faint">
              hybrid {dash(full.hybrid_score ?? full.rule_score)}/100 · {full.routing_score_basis === "hybrid" ? "ML + rules" : "rules only"}
            </span>
          </div>
        </div>
      </div>

      <Tabs tabs={["Overview", "Risk Signals", "Automation", "Details"]} active={tab} onChange={setTab} />

      <div className="space-y-3 px-5 pt-4">
        {tab === "Overview" && (
          <>
            <DrawerSection title="Identity">
              <Row k="Transaction" v={<span className="font-mono text-xs">{full.transaction_id}</span>} />
              <Row k="Risk band" v={<Pill value={full.risk_level} />} />
            </DrawerSection>
            <DrawerSection title="Scoring">
              <Row k="Rule score" v={<Mono>{dash(full.rule_score)}/100</Mono>} />
              <Row k="ML fraud probability" v={full.ml_fraud_probability != null
                ? <Mono>{(full.ml_fraud_probability * 100).toFixed(0)}%</Mono>
                : <span className="text-xs text-muted">model not trained</span>} />
              <Row k="Hybrid score" v={
                <span className="inline-flex items-center gap-1.5">
                  <Mono>{dash(full.hybrid_score ?? full.rule_score)}/100</Mono>
                  <span className="rounded-full bg-primary-soft px-1.5 py-px text-[10px] font-medium text-primary">used for routing</span>
                </span>} />
            </DrawerSection>
            <DrawerSection title="Disposition">
              <Row k="Recommended action" v={<span className="capitalize">{dash(full.recommended_action)}</span>} />
              <Row k="Automation decision" v={<Pill value={full.automation_decision} />} />
              <Row k="Human review required" v={full.human_review_required
                ? <Pill value="Escalated" />
                : <span className="text-xs text-muted">No — handled automatically</span>} />
            </DrawerSection>
          </>
        )}

        {tab === "Risk Signals" && (
          <>
            {full.rules_triggered?.length > 0 ? (
              <DrawerSection title={`Rules triggered (${full.rules_triggered.length})`} flush>
                {full.rules_triggered.map((r: any) => (
                  <div key={r.code} className="flex items-start justify-between gap-3 px-3.5 py-2.5">
                    <div className="min-w-0">
                      <span className="mr-2 font-mono text-[11px] text-faint">{r.code}</span>
                      <span className="text-[13px] font-medium">{r.name}</span>
                      <p className="mt-0.5 text-xxs text-muted">{r.detail}</p>
                    </div>
                    <span className="shrink-0 text-xs font-semibold text-danger">+{r.points}</span>
                  </div>
                ))}
              </DrawerSection>
            ) : (
              <DrawerSection title="Rules triggered">
                <p className="px-0 py-1 text-xs text-muted">None — within the customer&apos;s normal behavior profile.</p>
              </DrawerSection>
            )}
            <DrawerSection title="Signals">
              <Row k="Velocity (10 min)" v={<Mono>{dash(full.velocity_10_min)} txns</Mono>} />
              <Row k="Distance from home" v={<Mono>{full.distance_from_home_miles != null ? `${Math.round(full.distance_from_home_miles)} mi` : "—"}</Mono>} />
              <Row k="Merchant risk" v={<Mono>{full.merchant_risk_score?.toFixed(2) ?? "—"}</Mono>} />
              <Row k="Device" v={<span className="font-mono text-xs">{dash(full.device_id)}
                {full.is_new_device && <span className="ml-1.5 rounded bg-warn-soft px-1 py-px text-[10px] font-medium text-warn ring-1 ring-inset ring-warn-border">new</span>}</span>} />
              <Row k="Channel" v={<span className="capitalize">{full.transaction_type?.replace(/_/g, " ") || "—"}</span>} />
            </DrawerSection>
            <DrawerSection title="Score breakdown">
              <Row k="Rules contribution" v={<Mono>{dash(full.rule_score)}/100 × 0.4</Mono>} />
              <Row k="ML contribution" v={full.ml_fraud_probability != null
                ? <Mono>{(full.ml_fraud_probability * 100).toFixed(0)}/100 × 0.6</Mono>
                : <span className="text-xs text-muted">—</span>} />
              <Row k="Hybrid result" v={<Mono>{dash(full.hybrid_score ?? full.rule_score)}/100</Mono>} />
              {full.model_rule_agreement && <Row k="Model/rule agreement" v={<Pill value={full.model_rule_agreement} />} />}
            </DrawerSection>
          </>
        )}

        {tab === "Automation" && (
          <>
            <DrawerSection title="Routing decision">
              <Row k="Automation decision" v={<Pill value={full.automation_decision} />} />
              <Row k="Verification status" v={<Pill value={full.verification_status} />} />
              <Row k="Hold" v={full.hold_status
                ? <span className="text-xs font-medium text-warn">Transaction held</span>
                : <span className="text-xs text-muted">Not held</span>} />
              <Row k="Human review" v={full.human_review_required
                ? <Pill value="Escalated" />
                : <span className="text-xs text-muted">Not required</span>} />
            </DrawerSection>
            <DrawerSection title="Why this route">
              <p className="py-1 text-xs leading-relaxed text-muted">
                {WHY[full.automation_decision] || "Routing decision pending."}
              </p>
            </DrawerSection>
            <DrawerSection
              title="Customer verification"
              right={can("developer") && smsEligible && (
                <Button variant="ghost" onClick={sendTestSms} disabled={sending}>
                  <MessageSquare size={12} /> {sending ? "Sending…" : "Send test SMS"}
                </Button>
              )}
              flush
            >
              {sendMsg && <p className="px-3.5 pt-2 text-xxs text-muted">{sendMsg}</p>}
              {!notifs ? <div className="p-3.5"><Skeleton rows={2} /></div> : notifs.length === 0 ? (
                <p className="px-3.5 py-3 text-xs text-muted">No verification messages for this transaction.</p>
              ) : notifs.map((n) => (
                <div key={n.id} className="px-3.5 py-2.5">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-mono text-[11px] text-muted">{n.channel.toUpperCase()} · {n.provider} · {n.to_phone_masked}</span>
                    <Pill value={n.status} />
                  </div>
                  <p className="text-xs leading-relaxed text-muted">{n.message_body}</p>
                  <p className="mt-1 text-[10px] text-faint">
                    {n.sent_at ? `Sent ${fmtTime(n.sent_at)}` : `Created ${fmtTime(n.created_at)}`}
                    {n.metadata?.reason ? ` · ${n.metadata.reason.replace(/_/g, " ")}` : ""}
                    {n.metadata?.simulated ? " · simulated history" : ""}
                  </p>
                </div>
              ))}
            </DrawerSection>
          </>
        )}

        {tab === "Details" && (
          <>
            <DrawerSection title="Transaction">
              <Row k="Amount" v={<span className="font-medium">{fmtMoney(full.amount)}</span>} />
              <Row k="Timestamp" v={full.timestamp ? fmtTime(full.timestamp) : "—"} />
              <Row k="Type" v={<span className="capitalize">{full.transaction_type?.replace(/_/g, " ") || "—"}</span>} />
              <Row k="Currency" v={dash(full.currency)} />
            </DrawerSection>
            <DrawerSection title="Merchant">
              <Row k="Name" v={dash(full.merchant)} />
              <Row k="Category" v={<span className="capitalize">{full.merchant_category?.replace(/_/g, " ") || "—"}</span>} />
              <Row k="Location" v={`${dash(full.city)}, ${dash(full.state)}`} />
            </DrawerSection>
            <DrawerSection title="Customer">
              <Row k="Customer ID" v={<span className="font-mono text-xs">{dash(full.customer_id)}</span>} />
              <Row k="Device" v={<span className="font-mono text-xs">{dash(full.device_id)}{full.is_new_device ? " · new" : ""}</span>} />
            </DrawerSection>
          </>
        )}

        {/* ----- footer CTA, visible on every tab ----- */}
        <div className="pb-4 pt-1">
          {full.investigation_id ? (
            <Link href={`/investigations/${full.investigation_id}`}
              className="block rounded-lg bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary-hover">
              Open investigation {full.investigation_id}
            </Link>
          ) : (
            <p className="rounded-lg border border-dashed border-border py-2 text-center text-xs text-muted">
              No human investigation — handled by automated routing
              {full.verification_status === "pending_verification" ? " (awaiting customer verification)" : ""}.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function DrawerSection({ title, right, flush, children }: {
  title: string; right?: React.ReactNode; flush?: boolean; children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between bg-subtle/50 px-3.5 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-faint">{title}</p>
        {right}
      </div>
      <div className={flush ? "divide-y divide-border/60" : "px-3.5 py-1"}>{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/60 py-2 last:border-0">
      <span className="shrink-0 text-xs text-muted">{k}</span>
      <span className="min-w-0 text-right text-xs font-medium text-ink">{v}</span>
    </div>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-xs font-semibold tabular-nums">{children}</span>;
}

export default function TransactionsPage() {
  return (
    <Suspense>
      <TransactionsInner />
    </Suspense>
  );
}
