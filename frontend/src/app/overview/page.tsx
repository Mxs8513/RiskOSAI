"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import Shell, { PageHeader } from "@/components/shell";
import { Card, CardHeader, ChartTip, CHART, Pill, RiskScore, Skeleton, StatCard, Table } from "@/components/ui";
import { api, fmtMoney, fmtPct, fmtTime } from "@/lib/api";
import { DemoNotice } from "@/components/demo-notice";

function pctDelta(series: number[]): number | null {
  if (!series || series.length < 2) return null;
  const prev = series[series.length - 2], last = series[series.length - 1];
  if (prev === 0) return null;
  return ((last - prev) / prev) * 100;
}

export default function OverviewPage() {
  const [ov, setOv] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [invs, setInvs] = useState<any[] | null>(null);
  const [rules, setRules] = useState<any[] | null>(null);
  const [aiSummary, setAiSummary] = useState<{ summary: string; provider: string } | null>(null);

  useEffect(() => {
    api("/metrics/overview").then(setOv).catch(() => {});
    api("/metrics/charts").then(setCharts).catch(() => {});
    api("/investigations?limit=8").then(setInvs).catch(() => setInvs([]));
    api("/metrics/rules").then(setRules).catch(() => setRules([]));
    api("/metrics/daily-summary").then(setAiSummary).catch(() => {});
  }, []);

  const topRules = (rules || []).slice().sort((a, b) => b.trigger_count - a.trigger_count).slice(0, 5);
  const maxTriggers = topRules[0]?.trigger_count || 1;
  const queue = (invs || []).filter((i) => i.status === "Open" || i.status === "Hold for Review").slice(0, 5);
  const critical = (invs || []).filter((i) => i.risk_level === "Critical").slice(0, 6);

  const trend = charts?.daily_trend || [];
  const flaggedSeries = trend.map((d: any) => d.flagged);
  const criticalSeries = trend.map((d: any) => d.critical);
  const confirmedSeries = trend.map((d: any) => d.confirmed);

  return (
    <Shell>
      <PageHeader title="Overview" subtitle="Fraud operations at a glance — synthetic transaction stream" />

      <DemoNotice />

      {!ov ? <Skeleton rows={2} /> : (
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard label="Transactions processed" value={ov.transactions_processed.toLocaleString()} sub="all time" />
          <StatCard label="Flagged alerts" value={String(ov.flagged_alerts)} sub={`${ov.open_cases} open now`}
            spark={flaggedSeries} sparkColor={CHART.indigo} delta={pctDelta(flaggedSeries)} />
          <StatCard label="Critical cases" value={String(ov.critical_cases)} tone="danger"
            spark={criticalSeries} sparkColor={CHART.red} delta={pctDelta(criticalSeries)} />
          <StatCard label="Confirmed fraud" value={String(ov.confirmed_fraud)} tone="danger"
            spark={confirmedSeries} sparkColor={CHART.amber} />
          <StatCard label="Reviewer agreement" value={fmtPct(ov.reviewer_agreement_rate)} tone="success" />
          <StatCard label="False positive rate" value={fmtPct(ov.false_positive_rate)} />
          <StatCard label="Avg review time" value={`${Math.round(ov.avg_review_seconds)}s`} />
          <StatCard label="Top triggered rule" value={ov.most_triggered_rule || "—"} />
          <StatCard label="Automation rate" value={fmtPct(ov.automation_rate)} tone="success"
            sub="handled without a human" />
          <StatCard label="Human review avoided" value={String(ov.human_review_avoided)}
            sub="routed to verification instead" />
          <StatCard label="Verification required" value={String(ov.verification_required)}
            sub={`${ov.held_transactions} currently held`} />
          <StatCard label="Critical escalations" value={String(ov.critical_escalations)} tone="danger"
            sub="sent straight to humans" />
        </div>
      )}

      {aiSummary && (
        <Card className="mb-5">
          <div className="flex items-start gap-3 px-4 py-3.5">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Sparkles size={14} />
            </div>
            <div className="min-w-0">
              <div className="mb-0.5 flex items-center gap-2">
                <p className="text-xs font-semibold">AI Daily Summary</p>
                <span className="rounded-full bg-subtle px-1.5 py-px font-mono text-[10px] text-muted ring-1 ring-inset ring-border">
                  {aiSummary.provider}
                </span>
              </div>
              <p className="text-[13px] leading-relaxed text-muted">{aiSummary.summary}</p>
            </div>
          </div>
        </Card>
      )}

      <div className="mb-5 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="7-day risk trend" subtitle="Flagged, critical, and confirmed-fraud cases per day" />
          <div className="h-56 px-2 pb-3 pt-2">
            {charts ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={charts.daily_trend} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gFlag" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.indigo} stopOpacity={0.16} />
                      <stop offset="100%" stopColor={CHART.indigo} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gCrit" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.red} stopOpacity={0.1} />
                      <stop offset="100%" stopColor={CHART.red} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="date" tick={CHART.axis} axisLine={false} tickLine={false} dy={4} />
                  <YAxis tick={CHART.axis} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTip />} cursor={{ stroke: "#D4D4D8", strokeDasharray: "3 3" }} />
                  <Area type="monotone" dataKey="flagged" stroke={CHART.indigo} fill="url(#gFlag)" strokeWidth={1.75} name="Flagged" dot={false} activeDot={{ r: 3 }} />
                  <Area type="monotone" dataKey="critical" stroke={CHART.red} fill="url(#gCrit)" strokeWidth={1.75} name="Critical" dot={false} activeDot={{ r: 3 }} />
                  <Area type="monotone" dataKey="confirmed" stroke={CHART.amber} fill="none" strokeWidth={1.5} strokeDasharray="4 3" name="Confirmed" dot={false} activeDot={{ r: 3 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <Skeleton rows={4} />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Top triggered rules" subtitle="By trigger count, with false-positive rate" />
          <div className="space-y-3 px-4 py-4">
            {!rules ? <Skeleton rows={5} /> : topRules.map((r) => (
              <div key={r.rule_code}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <div className="min-w-0 truncate">
                    <span className="mr-2 font-mono text-[11px] text-faint">{r.rule_code}</span>
                    <span className="font-medium">{r.name}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 pl-2">
                    <span className="text-[10px] text-faint">FP {fmtPct(r.false_positive_rate)}</span>
                    <span className="font-mono font-semibold tabular-nums">{r.trigger_count}</span>
                  </div>
                </div>
                <div className="h-[5px] overflow-hidden rounded-full bg-subtle">
                  <div
                    className="h-full origin-left animate-grow-x rounded-full bg-gradient-to-r from-[#818CF8] to-primary"
                    style={{ width: `${(r.trigger_count / maxTriggers) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recent critical investigations"
            right={<Link href="/investigations" className="rounded-md text-xs font-medium text-primary hover:underline">View all</Link>} />
          <Table head={["Case", "Merchant", "Amount", "Risk", "Status"]} empty={critical.length === 0}>
            {critical.map((i) => (
              <tr key={i.investigation_id}>
                <td className="px-4 py-2.5">
                  <Link href={`/investigations/${i.investigation_id}`} className="rounded font-mono text-xs font-medium text-primary hover:underline">{i.investigation_id}</Link>
                  <div className="text-[10px] text-faint">{fmtTime(i.created_at)}</div>
                </td>
                <td className="px-4 py-2.5 text-[13px] font-medium">{i.merchant}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{fmtMoney(i.amount)}</td>
                <td className="px-4 py-2.5"><RiskScore score={i.risk_score} level={i.risk_level} /></td>
                <td className="px-4 py-2.5"><Pill value={i.status} /></td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card>
          <CardHeader title="Review queue" subtitle="Open cases awaiting a reviewer decision" />
          <Table head={["Case", "Customer", "Amount", "Risk", "AI recommends"]} empty={queue.length === 0}>
            {queue.map((i) => (
              <tr key={i.investigation_id}>
                <td className="px-4 py-2.5">
                  <Link href={`/investigations/${i.investigation_id}`} className="rounded font-mono text-xs font-medium text-primary hover:underline">{i.investigation_id}</Link>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{i.customer_id}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{fmtMoney(i.amount)}</td>
                <td className="px-4 py-2.5"><RiskScore score={i.risk_score} level={i.risk_level} /></td>
                <td className="px-4 py-2.5 text-xs font-medium capitalize text-ink">{i.recommended_action?.replace(/_/g, " ")}</td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </Shell>
  );
}
