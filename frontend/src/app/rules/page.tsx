"use client";

import { useCallback, useEffect, useState } from "react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, Pill, Skeleton, Table, Toast } from "@/components/ui";
import { api, can, fmtPct, fmtTime } from "@/lib/api";

export default function RulesPage() {
  const [rules, setRules] = useState<any[] | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const editable = can("rules:edit");

  const load = useCallback(async () => {
    try { setRules(await api("/rules")); } catch { setRules([]); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggle(rule: any) {
    const next = rule.status === "active" ? "disabled" : "active";
    try {
      await api(`/rules/${rule.id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
      setToast(`${rule.rule_code} ${next === "active" ? "enabled" : "disabled"}`);
      setTimeout(() => setToast(null), 2200);
      await load();
    } catch (e: any) {
      setToast(e.message); setTimeout(() => setToast(null), 2200);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Rules"
        subtitle="Deterministic fraud-scoring rules — every score is explainable, no black-box decisions"
      />
      <Card>
        {!rules ? <div className="p-4"><Skeleton rows={7} /></div> : (
          <Table head={["Rule", "Description", "Threshold", "Weight", "Triggers", "False positives", "FP rate", "Status", "Updated", editable ? "" : " "]}>
            {rules.map((r) => (
              <tr key={r.id} className="">
                <td className="px-4 py-2 whitespace-nowrap">
                  <span className="font-mono text-xs text-muted mr-2">{r.rule_code}</span>
                  <span className="text-sm font-medium">{r.name}</span>
                </td>
                <td className="px-4 py-2 text-xs text-muted max-w-xs">{r.description}</td>
                <td className="px-4 py-2 text-xs">{r.threshold}</td>
                <td className="px-4 py-2 text-xs tabular-nums">+{r.weight}</td>
                <td className="px-4 py-2 text-sm tabular-nums">{r.trigger_count}</td>
                <td className="px-4 py-2 text-sm tabular-nums">{r.false_positives}</td>
                <td className="px-4 py-2 text-sm tabular-nums">{fmtPct(r.false_positive_rate)}</td>
                <td className="px-4 py-2"><Pill value={r.status} /></td>
                <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">{fmtTime(r.updated_at)}</td>
                <td className="px-4 py-2">
                  {editable && (
                    <Button variant="ghost" onClick={() => toggle(r)}>
                      {r.status === "active" ? "Disable" : "Enable"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {!editable && (
        <p className="text-xxs text-muted mt-3">
          Rule editing requires the Risk Manager or Admin role.
        </p>
      )}
      <Toast message={toast} />
    </Shell>
  );
}
