"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Search, ShieldAlert, Sparkles } from "lucide-react";
import Shell, { PageHeader } from "@/components/shell";
import { Button, Card, CardHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

type QueryResult = {
  intent: string;
  answer: string;
  sources: { type: string; id: string }[];
  records: any[];
  provider: string | null;
  params?: Record<string, any>;
  confidence?: string;
  blocked?: boolean;
  alternatives?: string[];
};

function IntelligenceInner() {
  const params = useSearchParams();
  const [question, setQuestion] = useState(params.get("q") || "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<string[]>("/risk-intelligence/suggestions").then(setSuggestions).catch(() => {});
  }, []);

  useEffect(() => {
    const q = params.get("q");
    if (q) ask(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ask(q: string) {
    if (!q.trim()) return;
    setQuestion(q);
    setLoading(true);
    setError(null);
    try {
      setResult(await api<QueryResult>("/risk-intelligence/query", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      }));
    } catch (e: any) {
      setError(e.message);
      setResult(null);
    }
    setLoading(false);
  }

  function sourceHref(s: { type: string; id: string }) {
    if (s.type === "investigation") return `/investigations/${s.id}`;
    if (s.type === "transaction") return `/transactions?search=${s.id}`;
    if (s.type === "rule") return "/rules";
    if (s.type === "audit") return "/audit";
    if (s.type === "metrics") return "/metrics";
    return "#";
  }

  return (
    <Shell>
      <PageHeader
        title="Risk Intelligence"
        subtitle="Natural-language questions over transactions, investigations, rules, and audit logs — classified into safe query intents (the AI never writes SQL)"
      />

      <Card className="mb-4">
        <div className="p-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                className="w-full rounded-lg border border-border pl-9 pr-3 py-2.5 text-sm shadow-[0_1px_2px_rgba(9,9,11,0.04)] transition-[border-color,box-shadow] duration-150 placeholder:text-faint hover:border-border-strong focus:border-primary focus:outline-none focus:shadow-focus-primary"
                placeholder="Ask Reach about transactions, fraud alerts, rules, or audit logs..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ask(question)}
              />
            </div>
            <Button variant="primary" onClick={() => ask(question)} disabled={loading}>
              <Sparkles size={14} /> {loading ? "Analyzing…" : "Ask"}
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                className="text-xs border border-border rounded-full px-3 py-1 text-muted hover:border-primary/50 hover:text-ink transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {loading && <Card><div className="p-4"><Skeleton rows={4} /></div></Card>}
      {error && <Card><p className="p-4 text-sm text-danger">{error}</p></Card>}

      {result && !loading && (
        <div className="space-y-4">
          <Card>
            <CardHeader
              title={result.blocked ? "Request blocked" : "Answer"}
              subtitle={result.provider
                ? `Summarized by ${result.provider}`
                : result.blocked ? "Risk Intelligence is a read-only query layer" : undefined}
              right={result.blocked && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-danger-soft px-2 py-[3px] text-xxs font-medium text-danger ring-1 ring-inset ring-danger-border">
                  <ShieldAlert size={11} /> Unsafe request blocked
                </span>
              )}
            />
            <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3">
              <Chip label="intent" value={result.intent} />
              {result.confidence && <Chip label="confidence" value={result.confidence} />}
              {Object.entries(result.params || {}).map(([k, v]) => (
                v != null && v !== false && <Chip key={k} label={k} value={String(v)} />
              ))}
            </div>
            <p className="px-4 pb-4 text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
            {(result.alternatives?.length ?? 0) > 0 && (
              <div className="border-t border-border px-4 pb-4 pt-3">
                <p className="mb-1.5 text-xxs font-medium uppercase tracking-wide text-muted">
                  {result.blocked ? "Try a safe question instead" : "I can answer this a few ways"}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.alternatives!.map((s) => (
                    <button key={s} onClick={() => ask(s)}
                      className="rounded-full border border-border px-3 py-1 text-xs text-muted transition-colors hover:border-primary/50 hover:text-ink">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {result.sources.length > 0 && (
              <div className="px-4 pb-4 border-t border-border pt-3">
                <p className="text-xxs font-medium text-muted uppercase tracking-wide mb-1.5">Source records</p>
                <div className="flex flex-wrap gap-1.5">
                  {result.sources.map((s, i) => (
                    <Link
                      key={i}
                      href={sourceHref(s)}
                      className="font-mono text-xxs border border-border rounded px-2 py-1 text-primary hover:border-primary/60"
                    >
                      {s.type}:{s.id}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {result.records.length > 0 && (
            <Card>
              <CardHeader title="Retrieved records" subtitle="Raw structured data behind the answer" />
              <div className="px-4 pb-4 overflow-x-auto">
                <pre className="bg-bg rounded-lg border border-border p-3 text-xxs leading-relaxed font-mono whitespace-pre-wrap">
                  {JSON.stringify(result.records, null, 2)}
                </pre>
              </div>
            </Card>
          )}
        </div>
      )}
    </Shell>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-subtle px-2 py-[3px] text-[10px] ring-1 ring-inset ring-border">
      <span className="text-faint">{label}</span>
      <span className="font-mono font-medium text-muted">{value}</span>
    </span>
  );
}

export default function IntelligencePage() {
  return (
    <Suspense>
      <IntelligenceInner />
    </Suspense>
  );
}
