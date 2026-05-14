"use client";

import { useCountUp } from "../../lib/hooks/useCountUp";
import type { UploadStatus } from "../../lib/types";

function NumberCell({ value, label }: { value: string; label: string }) {
  return (
    <div className="space-y-2">
      <p className="r-eyebrow">{label}</p>
      <p className="r-serif text-4xl italic leading-none text-[var(--r-ink)]">
        {value}
      </p>
    </div>
  );
}

export function ReportHero({ upload }: { upload: UploadStatus }) {
  const classified = useCountUp(upload.linhas_classificadas);
  const estSuppliers =
    upload.clusters_com_shortlist * upload.shortlist_config.size;
  const estSuppliersAnimated = useCountUp(estSuppliers);

  return (
    <section
      className="r-rise grid grid-cols-1 gap-0 border-b r-rule pb-10 lg:grid-cols-[2fr_1fr]"
      style={{ animationDelay: "80ms" }}
    >
      {/* Hero — left two thirds */}
      <div className="lg:border-r r-rule lg:pr-10">
        <p className="r-eyebrow">Linhas classificadas</p>
        <div className="mt-4 flex items-baseline gap-6">
          <span className="r-serif text-[88px] italic leading-[0.9] tracking-tight text-[var(--r-ink)] sm:text-[112px]">
            {classified.toLocaleString("pt-BR")}
          </span>
          <span className="r-serif text-2xl italic text-[var(--r-ink-2)]">
            de {upload.linhas_total.toLocaleString("pt-BR")}
          </span>
        </div>
        <div
          aria-hidden
          className="mt-3 h-[2px] origin-left bg-[var(--r-accent)]"
          style={{
            width: `${
              upload.linhas_total > 0
                ? Math.min(
                    100,
                    (upload.linhas_classificadas / upload.linhas_total) * 100,
                  )
                : 0
            }%`,
            transition: "width 1200ms cubic-bezier(.16,1,.3,1)",
          }}
        />
      </div>

      {/* Secondary stats — right third, stacked vertically */}
      <div className="mt-8 grid grid-cols-1 divide-y r-rule lg:mt-0 lg:pl-10">
        <div className="pb-6 lg:pb-6">
          <NumberCell
            label="Categorias identificadas"
            value={upload.clusters_total.toLocaleString("pt-BR")}
          />
          <p className="mt-2 text-xs text-[var(--r-ink-2)]">
            {upload.clusters_classificados} classificadas ·{" "}
            {upload.clusters_com_shortlist} com shortlist
          </p>
        </div>
        <div className="py-6">
          <NumberCell
            label="Fornecedores estimados"
            value={estSuppliersAnimated.toLocaleString("pt-BR")}
          />
          <p className="mt-2 text-xs text-[var(--r-ink-2)]">
            top {upload.shortlist_config.size} por categoria
          </p>
        </div>
      </div>
    </section>
  );
}
