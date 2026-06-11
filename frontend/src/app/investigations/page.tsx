"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Shell, { PageHeader } from "@/components/shell";
import { Card, Pill, RiskScore, Select, Skeleton, Table } from "@/components/ui";
import { api, fmtMoney, fmtTime } from "@/lib/api";

const STATUSES = ["Open", "Hold for Review", "Escalated", "Cleared", "Confirmed Fraud"];
const LEVELS = ["High", "Critical"];

export default function InvestigationsPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [status, setStatus] = useState("");
  const [level, setLevel] = useState("");

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ limit: "100" });
    if (status) qs.set("status", status);
    if (level) qs.set("risk_level", level);
    try { setRows(await api(`/investigations?${qs.toString()}`)); } catch { setRows([]); }
  }, [status, level]);

  useEffect(() => { load(); }, [load]);

  return (
    <Shell>
      <PageHeader title="Investigations" subtitle="Every flagged transaction becomes an auditable investigation case" />
      <div className="flex items-center gap-2 mb-4">
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
        <Select value={level} onChange={setLevel} options={LEVELS} placeholder="All risk levels" />
      </div>
      <Card>
        {!rows ? <div className="p-4"><Skeleton rows={8} /></div> : (
          <Table head={["Case", "Transaction", "Customer", "Merchant", "Amount", "Risk", "Status", "Policy", "Reviewer", "Created"]} empty={rows.length === 0}>
            {rows.map((i) => (
              <tr key={i.investigation_id} className="">
                <td className="px-4 py-2">
                  <Link href={`/investigations/${i.investigation_id}`} className="text-primary font-mono text-xs hover:underline">
                    {i.investigation_id}
                  </Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs">{i.transaction_id}</td>
                <td className="px-4 py-2 font-mono text-xs">{i.customer_id}</td>
                <td className="px-4 py-2 text-sm">{i.merchant}</td>
                <td className="px-4 py-2 text-sm tabular-nums">{fmtMoney(i.amount)}</td>
                <td className="px-4 py-2"><RiskScore score={i.risk_score} level={i.risk_level} /></td>
                <td className="px-4 py-2"><Pill value={i.status} /></td>
                <td className="px-4 py-2">{i.policy_check_status ? <Pill value={i.policy_check_status} /> : <span className="text-xxs text-muted">—</span>}</td>
                <td className="px-4 py-2 text-xs">{i.assigned_to || <span className="text-muted">Unassigned</span>}</td>
                <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">{fmtTime(i.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </Shell>
  );
}
