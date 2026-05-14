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
      className="r-rise space-y-5 border-b r-rule py-10"
      style={{ animationDelay: "320ms" }}
    >
      <p className="r-eyebrow">Top categorias por número de linhas</p>
      <ol className="space-y-3">
        {top.map((c, i) => {
          const label = c.nome_cluster_refinado ?? c.nome_cluster;
          const widthPct = max > 0 ? (c.num_linhas / max) * 100 : 0;
          return (
            <li key={c.id} className="group">
              <Link
                href={`/clusters/${c.id}`}
                className="flex items-center gap-4 py-2"
              >
                <span className="r-serif w-6 shrink-0 text-base italic text-[var(--r-ink-2)]">
                  {i + 1}.
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <span
                      className="r-serif truncate text-lg italic text-[var(--r-ink)] group-hover:text-[var(--r-accent)] transition-colors"
                      title={label}
                    >
                      {label}
                    </span>
                    <span className="r-mono shrink-0 text-sm text-[var(--r-ink)]">
                      {c.num_linhas.toLocaleString("pt-BR")}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-3">
                    <div className="h-[3px] flex-1 bg-[var(--r-rule)]">
                      <div
                        className="h-full"
                        style={{
                          width: `${widthPct}%`,
                          backgroundColor:
                            i === 0 ? "var(--r-accent)" : "var(--r-ink)",
                          transition: "width 900ms cubic-bezier(.16,1,.3,1)",
                        }}
                      />
                    </div>
                    {c.cnae && (
                      <span className="r-mono text-xs text-[var(--r-ink-2)]">
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
