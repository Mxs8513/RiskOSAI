"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, Pill, Select, Skeleton, Table } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";

const STATUSES = ["queued", "sent", "failed"];

export default function NotificationsPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ limit: "100" });
    if (status) qs.set("status", status);
    try { setRows(await api(`/notifications?${qs.toString()}`)); } catch { setRows([]); }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  return (
    <Shell>
      <PageHeader
        title="Notifications"
        subtitle="Outbound customer verification messages — strict templates only, sent solely to the configured demo phone"
        right={<Button variant="ghost" onClick={load} title="Refresh"><RefreshCw size={14} /></Button>}
      />
      <div className="mb-4">
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
      </div>
      <Card>
        {!rows ? <div className="p-4"><Skeleton rows={8} /></div> : (
          <Table head={["Time", "Transaction", "Channel", "To", "Message", "Status"]} empty={rows.length === 0}>
            {rows.map((n) => (
              <tr key={n.id}>
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[11px] text-faint">
                  {fmtTime(n.sent_at || n.created_at)}
                </td>
                <td className="px-4 py-2.5">
                  <Link href={`/transactions?search=${n.transaction_id}`} className="font-mono text-xs text-primary hover:underline">
                    {n.transaction_id}
                  </Link>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted">{n.channel.toUpperCase()} · {n.provider}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{n.to_phone_masked}</td>
                <td className="max-w-md px-4 py-2.5 text-xs text-muted">
                  <span className="line-clamp-2">{n.message_body}</span>
                </td>
                <td className="px-4 py-2.5"><Pill value={n.status} /></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </Shell>
  );
}
