"use client";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, AreaChart, Area, Legend,
} from "recharts";
import Shell, { PageHeader } from "@/components/shell";
import { Card, CardHeader, ChartTip, CHART, Skeleton, StatCard, Table } from "@/components/ui";
import { api, fmtPct } from "@/lib/api";

const OUTCOME_COLORS: Record<string, string> = {
  "true positive": CHART.red,
  "false positive": CHART.green,
  "pending verification": CHART.amber,
  escalated: CHART.indigo,
  unresolved: CHART.zinc,
};

const legendStyle = { fontSize: 11, color: "#71717A" };
const axisProps = { tick: CHART.axis, axisLine: false as const, tickLine: false as const };

export default function MetricsPage() {
  const [ov, setOv] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [rules, setRules] = useState<any[] | null>(null);

  useEffect(() => {
    api("/metrics/overview").then(setOv).catch(() => {});
    api("/metrics/charts").then(setCharts).catch(() => {});
    api("/metrics/rules").then(setRules).catch(() => setRules([]));
  }, []);

  const fpByRule = (rules || []).map((r) => ({
    rule: r.rule_code, false_positives: r.false_positives, true_positives: r.true_positives,
  }));

  const totalOutcomes = (charts?.reviewer_outcomes || []).reduce((s: number, o: any) => s + o.count, 0);

  return (
    <Shell>
      <PageHeader title="Metrics" subtitle="Closed-loop analytics — reviewer decisions feed back into false-positive and agreement metrics" />

      {!ov ? <Skeleton rows={2} /> : (
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard label="Total investigations" value={String(ov.flagged_alerts)} />
          <StatCard label="Confirmed fraud" value={String(ov.confirmed_fraud)} tone="danger" />
          <StatCard label="Cleared (false positives)" value={String(ov.cleared)} tone="success" />
          <StatCard label="False positive rate" value={fmtPct(ov.false_positive_rate)} />
          <StatCard label="Reviewer agreement" value={fmtPct(ov.reviewer_agreement_rate)} tone="success" />
          <StatCard label="AI recommendation accuracy" value={fmtPct(ov.ai_recommendation_accuracy)} />
          <StatCard label="Avg review time" value={`${Math.round(ov.avg_review_seconds)}s`} />
          <StatCard label="Most triggered rule" value={ov.most_triggered_rule || "—"} />
        </div>
      )}

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="False positives by rule" subtitle="Reviewer-confirmed outcomes per triggered rule" />
          <div className="h-60 px-2 pb-3 pt-2">
            {rules ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={fpByRule} margin={{ top: 8, right: 12, left: -18, bottom: 0 }} barGap={3}>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="rule" {...axisProps} dy={4} />
                  <YAxis {...axisProps} allowDecimals={false} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(9,9,11,0.03)" }} />
                  <Legend wrapperStyle={legendStyle} iconType="circle" iconSize={7} />
                  <Bar dataKey="true_positives" name="True positives" fill={CHART.red} fillOpacity={0.85} radius={[4, 4, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="false_positives" name="False positives" fill={CHART.green} fillOpacity={0.85} radius={[4, 4, 0, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton rows={5} />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Risk score distribution" subtitle="All scored transactions, bucketed by 10" />
          <div className="h-60 px-2 pb-3 pt-2">
            {charts ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={charts.score_distribution} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gDist" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#818CF8" />
                      <stop offset="100%" stopColor={CHART.indigo} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="bucket" {...axisProps} dy={4} />
                  <YAxis {...axisProps} allowDecimals={false} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(9,9,11,0.03)" }} />
                  <Bar dataKey="count" name="Transactions" fill="url(#gDist)" radius={[4, 4, 0, 0]} maxBarSize={26} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton rows={5} />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Reviewer outcomes" subtitle="Human decisions across resolved cases" />
          <div className="relative h-60 px-2 pb-3">
            {charts ? (
              <>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={charts.reviewer_outcomes} dataKey="count" nameKey="outcome"
                      innerRadius={56} outerRadius={80} paddingAngle={3} cornerRadius={4} strokeWidth={0}
                    >
                      {charts.reviewer_outcomes.map((o: any) => (
                        <Cell key={o.outcome} fill={OUTCOME_COLORS[o.outcome] || CHART.zinc} fillOpacity={0.9} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTip />} />
                    <Legend wrapperStyle={legendStyle} iconType="circle" iconSize={7} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-7">
                  <span className="text-xl font-semibold tabular-nums tracking-[-0.02em]">{totalOutcomes}</span>
                  <span className="text-[10px] uppercase tracking-[0.08em] text-faint">decisions</span>
                </div>
              </>
            ) : <Skeleton rows={5} />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Daily fraud trend" subtitle="Flagged vs critical vs confirmed, last 7 days" />
          <div className="h-60 px-2 pb-3 pt-2">
            {charts ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={charts.daily_trend} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gFlag2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.indigo} stopOpacity={0.16} />
                      <stop offset="100%" stopColor={CHART.indigo} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="date" {...axisProps} dy={4} />
                  <YAxis {...axisProps} allowDecimals={false} />
                  <Tooltip content={<ChartTip />} cursor={{ stroke: "#D4D4D8", strokeDasharray: "3 3" }} />
                  <Legend wrapperStyle={legendStyle} iconType="circle" iconSize={7} />
                  <Area type="monotone" dataKey="flagged" name="Flagged" stroke={CHART.indigo} fill="url(#gFlag2)" strokeWidth={1.75} dot={false} activeDot={{ r: 3 }} />
                  <Area type="monotone" dataKey="critical" name="Critical" stroke={CHART.red} fill="none" strokeWidth={1.75} dot={false} activeDot={{ r: 3 }} />
                  <Area type="monotone" dataKey="confirmed" name="Confirmed" stroke={CHART.amber} fill="none" strokeWidth={1.5} strokeDasharray="4 3" dot={false} activeDot={{ r: 3 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <Skeleton rows={5} />}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Highest-risk merchants" subtitle="By average risk score (min 3 transactions)" />
          <Table head={["Merchant", "Avg risk score", "Transactions"]} empty={!charts || charts.top_risk_merchants.length === 0}>
            {(charts?.top_risk_merchants || []).map((m: any) => (
              <tr key={m.name}>
                <td className="px-4 py-2.5 text-[13px] font-medium">{m.name}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{(m.avg_risk_score ?? 0).toFixed(1)}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{m.transactions}</td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card>
          <CardHeader title="Rule performance" subtitle="Trigger counts and false-positive rates" />
          <Table head={["Rule", "Triggers", "TP", "FP", "FP rate"]} empty={!rules || rules.length === 0}>
            {(rules || []).map((r) => (
              <tr key={r.rule_code}>
                <td className="px-4 py-2.5 text-[13px]">
                  <span className="mr-2 font-mono text-xs text-faint">{r.rule_code}</span>
                  <span className="font-medium">{r.name}</span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{r.trigger_count}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{r.true_positives}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{r.false_positives}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums">{fmtPct(r.false_positive_rate)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </Shell>
  );
}
