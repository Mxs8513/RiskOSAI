"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, FlaskConical, Play, XCircle } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, CardHeader, Pill, RiskScore, Select, Skeleton, Table, Toast } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";

const RULE_CODES = ["R-001", "R-002", "R-003", "R-004", "R-005", "R-006", "R-007"];

const DEFAULT_PAYLOAD = {
  amount: 940.0,
  user_avg_amount: 80.0,
  is_new_device: true,
  velocity_10_min: 5,
  distance_from_home_miles: 20,
  merchant_risk_score: 0.4,
  transaction_type: "card_not_present",
  dataset_label: false,
};

export default function DeveloperPage() {
  const [rule, setRule] = useState("R-002");
  const [scenarios, setScenarios] = useState<any | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [payloadText, setPayloadText] = useState(JSON.stringify(DEFAULT_PAYLOAD, null, 2));
  const [runResult, setRunResult] = useState<any | null>(null);
  const [samples, setSamples] = useState<any>(null);
  const [history, setHistory] = useState<any[] | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api("/developer/sample-payloads").then(setSamples).catch(() => {});
    loadHistory();
  }, []);

  async function loadHistory() {
    try { setHistory(await api("/developer/scenario-history")); } catch { setHistory([]); }
  }

  function flash(m: string) { setToast(m); setTimeout(() => setToast(null), 2500); }

  async function generate() {
    setGenLoading(true);
    try {
      const res = await api("/developer/generate-scenario", {
        method: "POST",
        body: JSON.stringify({ rule_code: rule, count: 4 }),
      });
      setScenarios(res);
      flash(`${res.summary.passed}/${res.summary.total} scenarios passed for ${rule}`);
      loadHistory();
    } catch (e: any) { flash(e.message); }
    setGenLoading(false);
  }

  async function runScenario() {
    try {
      const body = JSON.parse(payloadText);
      setRunResult(await api("/developer/run-scenario", { method: "POST", body: JSON.stringify(body) }));
    } catch (e: any) {
      flash(e instanceof SyntaxError ? "Invalid JSON payload" : e.message);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Developer Console"
        subtitle="Software-factory tooling: generate edge-case scenarios per rule and run ad-hoc payloads against the risk engine"
      />

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <CardHeader
            title="Generate test scenarios"
            subtitle="AI generates edge cases targeting one rule; each is replayed through the deterministic risk engine"
          />
          <div className="px-4 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <Select value={rule} onChange={setRule} options={RULE_CODES} placeholder="Select rule" />
              <Button variant="primary" onClick={generate} disabled={genLoading}>
                <FlaskConical size={14} /> {genLoading ? "Generating…" : "Generate 4 scenarios"}
              </Button>
            </div>
            {scenarios && (
              <div className="space-y-2">
                <p className="text-xs text-muted">
                  {scenarios.summary.passed}/{scenarios.summary.total} passed (scenario flagged as expected and {scenarios.rule_code} triggered)
                </p>
                {scenarios.scenarios.map((s: any, i: number) => (
                  <div key={i} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {s.passed
                          ? <CheckCircle2 size={15} className="text-success" />
                          : <XCircle size={15} className="text-danger" />}
                        <span className="text-sm font-medium">Scenario {i + 1}</span>
                        <span className="text-xxs text-muted">expected: {s.expected}</span>
                      </div>
                      <RiskScore score={s.score} level={s.risk_level} />
                    </div>
                    <div className="flex flex-wrap gap-1 mb-1.5">
                      {s.rules_triggered.map((c: string) => (
                        <span key={c} className={`font-mono text-xxs rounded px-1.5 py-0.5 border ${c === scenarios.rule_code ? "border-primary text-primary bg-primary-soft" : "border-border text-muted"}`}>{c}</span>
                      ))}
                    </div>
                    <pre className="text-xxs font-mono bg-bg border border-border rounded p-2 whitespace-pre-wrap">
                      {JSON.stringify(s.payload, null, 1)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Run scenario" subtitle="POST an arbitrary payload through /developer/run-scenario" />
            <div className="px-4 pb-4">
              <textarea
                className="w-full rounded-lg border border-border p-3 font-mono text-xs mb-2 shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-[border-color,box-shadow] duration-150 placeholder:text-faint hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary"
                rows={10}
                value={payloadText}
                onChange={(e) => setPayloadText(e.target.value)}
                spellCheck={false}
              />
              <Button variant="primary" onClick={runScenario}><Play size={14} /> Score payload</Button>
              {runResult && (
                <div className="mt-3 rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between mb-2">
                    <RiskScore score={runResult.score} level={runResult.risk_level} />
                    <Pill value={runResult.suggested_status} />
                  </div>
                  <p className="text-xs text-muted mb-2 capitalize">Recommended action: {runResult.recommended_action}</p>
                  <div className="space-y-1">
                    {runResult.rules_triggered.map((r: any) => (
                      <div key={r.code} className="flex justify-between text-xs border border-border rounded px-2 py-1">
                        <span><span className="font-mono text-muted mr-1.5">{r.code}</span>{r.detail}</span>
                        <span className="text-danger font-medium">+{r.points}</span>
                      </div>
                    ))}
                    {runResult.rules_triggered.length === 0 && <p className="text-xs text-muted">No rules triggered.</p>}
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Sample API payloads" />
            <div className="px-4 pb-4 space-y-2">
              {samples ? Object.entries(samples).map(([endpoint, body]) => (
                <div key={endpoint}>
                  <p className="font-mono text-xxs text-muted mb-1">{endpoint}</p>
                  <pre className="text-xxs font-mono bg-bg border border-border rounded p-2 whitespace-pre-wrap">
                    {JSON.stringify(body, null, 1)}
                  </pre>
                </div>
              )) : <Skeleton rows={3} />}
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Scenario history" subtitle="Previously generated test scenarios (persisted + audit logged)" />
        {!history ? <div className="p-4"><Skeleton rows={4} /></div> : (
          <Table head={["Time", "Rule", "Expected", "Actual", "Result"]} empty={history.length === 0}>
            {history.map((s) => (
              <tr key={s.id} className="">
                <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">{fmtTime(s.created_at)}</td>
                <td className="px-4 py-2 font-mono text-xs">{s.rule_code}</td>
                <td className="px-4 py-2 text-xs">{s.expected}</td>
                <td className="px-4 py-2 text-xs">{s.actual}</td>
                <td className="px-4 py-2">
                  {s.passed
                    ? <span className="inline-flex items-center gap-1 text-xs text-success"><CheckCircle2 size={13} /> Pass</span>
                    : <span className="inline-flex items-center gap-1 text-xs text-danger"><XCircle size={13} /> Fail</span>}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Toast message={toast} />
    </Shell>
  );
}
