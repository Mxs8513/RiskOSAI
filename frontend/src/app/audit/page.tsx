"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Card, Select, Skeleton, Table } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";

const EVENT_TYPES = [
  "user_logged_in", "transaction_processed", "risk_score_generated", "investigation_created",
  "ai_report_generated", "policy_check_completed", "reviewer_decision_submitted",
  "case_status_updated", "case_status_overridden", "risk_intelligence_query", "test_scenario_generated",
  "rule_updated",
];

export default function AuditPage() {
  const [data, setData] = useState<{ limited_view: boolean; logs: any[] } | null>(null);
  const [eventType, setEventType] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ limit: "120" });
    if (eventType) qs.set("event_type", eventType);
    try { setData(await api(`/audit-logs?${qs.toString()}`)); } catch { setData({ limited_view: true, logs: [] }); }
  }, [eventType]);

  useEffect(() => { load(); }, [load]);

  return (
    <Shell>
      <PageHeader title="Audit Logs" subtitle="Immutable trail of every action in the system — login to reviewer decision" />

      {data?.limited_view && (
        <div className="flex items-center gap-2 bg-info-soft border border-info/20 text-info rounded-lg px-3 py-2 text-xs mb-4">
          <Info size={14} />
          Limited view — your role can only see case-workflow events. Risk Managers and Admins see the full audit trail.
        </div>
      )}

      <div className="flex items-center gap-2 mb-4">
        <Select value={eventType} onChange={setEventType} options={EVENT_TYPES} placeholder="All event types" />
      </div>

      <Card>
        {!data ? <div className="p-4"><Skeleton rows={10} /></div> : (
          <Table head={["", "Time", "Event", "Actor", "Transaction", "Investigation", "Message"]} empty={(data.logs?.length ?? 0) === 0}>
            {(data.logs ?? []).map((a) => (
              <>
                <tr
                  key={a.id}
                  className="cursor-pointer"
                  onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                >
                  <td className="pl-4 py-2 text-muted">
                    {expanded === a.id ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">{fmtTime(a.timestamp)}</td>
                  <td className="px-4 py-2"><span className="font-mono text-xxs border border-border rounded px-1.5 py-0.5">{a.event_type}</span></td>
                  <td className="px-4 py-2 text-xs">{a.actor}<span className="text-muted"> · {a.actor_role || "system"}</span></td>
                  <td className="px-4 py-2 font-mono text-xs">{a.transaction_id || "—"}</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {a.investigation_id ? (
                      <Link href={`/investigations/${a.investigation_id}`} className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
                        {a.investigation_id}
                      </Link>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs max-w-md truncate">{a.message}</td>
                </tr>
                {expanded === a.id && (
                  <tr key={`${a.id}-meta`} className="bg-bg/60">
                    <td colSpan={7} className="px-6 py-3">
                      <p className="text-xxs font-medium text-muted uppercase tracking-wide mb-1">Metadata</p>
                      <pre className="text-xxs font-mono bg-card rounded-lg border border-border p-3 whitespace-pre-wrap">
                        {JSON.stringify(a.metadata || {}, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </Table>
        )}
      </Card>
    </Shell>
  );
}
