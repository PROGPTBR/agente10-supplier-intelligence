"use client";

import { useCountUp } from "../../lib/hooks/useCountUp";
import type { UploadStatus } from "../../lib/types";

function StatCell({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="space-y-2">
      <p className="r-eyebrow">{label}</p>
      <p className="r-display text-3xl text-[var(--r-ink)]">{value}</p>
      {hint && <p className="text-xs text-[var(--r-ink-2)]">{hint}</p>}
    </div>
  );
}

export function ReportHero({ upload }: { upload: UploadStatus }) {
  const classified = useCountUp(upload.linhas_classificadas);
  const estSuppliers =
    upload.clusters_com_shortlist * upload.shortlist_config.size;
  const estSuppliersAnimated = useCountUp(estSuppliers);
  const pct =
    upload.linhas_total > 0
      ? Math.min(100, (upload.linhas_classificadas / upload.linhas_total) * 100)
      : 0;

  return (
    <section
      className="r-rise mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]"
      style={{ animationDelay: "80ms" }}
    >
      {/* Hero card */}
      <div
        className="r-card relative overflow-hidden p-8"
        style={{
          background:
            "linear-gradient(140deg, #ffffff 0%, #f7f5ff 60%, #efeaff 100%)",
        }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -right-8 -top-8 h-44 w-44 rounded-full"
          style={{
            background:
              "radial-gradient(closest-side, rgba(91,63,229,0.18), transparent)",
          }}
        />
        <p className="r-eyebrow">Linhas classificadas</p>
        <div className="mt-3 flex items-baseline gap-5">
          <span className="r-display text-[88px] leading-[0.9] tracking-tight text-[var(--r-ink)] sm:text-[112px]">
            {classified.toLocaleString("pt-BR")}
          </span>
          <span className="r-display text-2xl text-[var(--r-ink-2)]">
            / {upload.linhas_total.toLocaleString("pt-BR")}
          </span>
        </div>
        <div className="mt-6 h-1.5 w-full overflow-hidden rounded-full bg-[var(--r-surface-2)]">
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              background:
                "linear-gradient(90deg, #8C84FF 0%, #5B3FE5 60%, #2C1666 100%)",
              transition: "width 1200ms cubic-bezier(.16,1,.3,1)",
            }}
          />
        </div>
        <div className="mt-3 flex items-baseline justify-between text-xs text-[var(--r-ink-2)]">
          <span>Progresso da classificação</span>
          <span className="r-mono">{pct.toFixed(1)}%</span>
        </div>
      </div>

      {/* Secondary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-1">
        <div className="r-card p-6">
          <StatCell
            label="Categorias identificadas"
            value={upload.clusters_total.toLocaleString("pt-BR")}
            hint={`${upload.clusters_classificados} classificadas · ${upload.clusters_com_shortlist} com shortlist`}
          />
        </div>
        <div className="r-card p-6">
          <StatCell
            label="Fornecedores estimados"
            value={estSuppliersAnimated.toLocaleString("pt-BR")}
            hint={`top ${upload.shortlist_config.size} por categoria`}
          />
        </div>
      </div>
    </section>
  );
}
