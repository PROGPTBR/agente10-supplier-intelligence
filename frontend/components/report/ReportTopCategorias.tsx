"use client";

import Link from "next/link";
import type { ClusterSummary } from "../../lib/types";

export function ReportTopCategorias({
  clusters,
}: {
  clusters: ClusterSummary[];
}) {
  const top = [...clusters]
    .sort((a, b) => b.num_linhas - a.num_linhas)
    .slice(0, 5);

  if (top.length === 0) return null;
  const max = top[0].num_linhas;

  return (
    <section
      className="r-card r-rise mt-6 space-y-5 p-7"
      style={{ animationDelay: "280ms" }}
    >
      <p className="r-eyebrow">Top categorias por número de linhas</p>
      <ol className="space-y-2">
        {top.map((c, i) => {
          const label = c.nome_cluster_refinado ?? c.nome_cluster;
          const widthPct = max > 0 ? (c.num_linhas / max) * 100 : 0;
          return (
            <li key={c.id}>
              <Link
                href={`/clusters/${c.id}`}
                className="group flex items-center gap-4 rounded-xl py-2.5 transition-colors hover:bg-[var(--r-surface-2)] px-2 -mx-2"
              >
                <span className="r-mono w-6 shrink-0 text-xs font-semibold text-[var(--r-ink-3)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <span
                      className="r-display truncate text-base text-[var(--r-ink)] group-hover:text-[var(--r-primary)] transition-colors"
                      title={label}
                    >
                      {label}
                    </span>
                    <span className="r-mono shrink-0 text-sm font-semibold text-[var(--r-ink)]">
                      {c.num_linhas.toLocaleString("pt-BR")}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-3">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-[var(--r-surface-2)]">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${widthPct}%`,
                          background:
                            i === 0
                              ? "linear-gradient(90deg, #8C84FF, #5B3FE5)"
                              : "#5B3FE5",
                          transition: "width 900ms cubic-bezier(.16,1,.3,1)",
                        }}
                      />
                    </div>
                    {c.cnae && (
                      <span className="r-mono text-[10px] text-[var(--r-ink-3)]">
                        CNAE {c.cnae}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
