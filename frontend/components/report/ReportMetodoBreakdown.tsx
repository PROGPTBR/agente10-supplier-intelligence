"use client";

import type { ClusterSummary } from "../../lib/types";

interface Segment {
  key: string;
  label: string;
  color: string;
  count: number;
}

const SEGMENT_ORDER: Array<Omit<Segment, "count">> = [
  { key: "revisado_humano", label: "Revisado humano", color: "#10B981" },
  { key: "curator", label: "Curator (LLM)", color: "#5B3FE5" },
  { key: "retrieval", label: "Retrieval", color: "#8C84FF" },
  { key: "cache", label: "Cache", color: "#A4C5FF" },
  { key: "golden", label: "Golden seed", color: "#F59E0B" },
  { key: "manual_pending", label: "Pendente manual", color: "#EF4444" },
];

export function ReportMetodoBreakdown({
  clusters,
}: {
  clusters: ClusterSummary[];
}) {
  const counts = clusters.reduce<Record<string, number>>((acc, c) => {
    const k = c.cnae_metodo ?? "manual_pending";
    acc[k] = (acc[k] ?? 0) + 1;
    return acc;
  }, {});

  const segments: Segment[] = SEGMENT_ORDER.map((s) => ({
    ...s,
    count: counts[s.key] ?? 0,
  })).filter((s) => s.count > 0);

  const total = segments.reduce((sum, s) => sum + s.count, 0);
  if (total === 0) return null;

  return (
    <section
      className="r-card r-rise mt-6 space-y-5 p-7"
      style={{ animationDelay: "200ms" }}
    >
      <div className="flex items-baseline justify-between gap-4">
        <p className="r-eyebrow">Distribuição por método de classificação</p>
        <p className="r-mono text-xs text-[var(--r-ink-2)]">
          {total} {total === 1 ? "categoria" : "categorias"}
        </p>
      </div>

      <div
        role="img"
        aria-label={`Distribuição de métodos: ${segments
          .map((s) => `${s.label}: ${s.count}`)
          .join(", ")}`}
        className="flex h-3 w-full overflow-hidden rounded-full bg-[var(--r-surface-2)]"
      >
        {segments.map((s) => (
          <div
            key={s.key}
            title={`${s.label}: ${s.count}`}
            style={{
              width: `${(s.count / total) * 100}%`,
              backgroundColor: s.color,
              transition: "width 800ms cubic-bezier(.16,1,.3,1)",
            }}
          />
        ))}
      </div>

      <ul className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
        {segments.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: s.color }}
            />
            <span className="truncate text-[var(--r-ink-2)]">{s.label}</span>
            <span className="r-mono ml-auto font-semibold text-[var(--r-ink)]">
              {s.count}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
