"use client";

import { useState } from "react";
import type { ShortlistEntry } from "../../lib/types";
import { apiDownload } from "../../lib/api/client";

interface Props {
  clusterId: string;
  selected: ShortlistEntry[];
  onClear: () => void;
  onRemove: (cnpjBasico: string) => void;
}

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function SelectionPanel({
  clusterId,
  selected,
  onClear,
  onRemove,
}: Props) {
  const [exporting, setExporting] = useState(false);
  if (selected.length === 0) return null;

  const totalCapital = selected.reduce(
    (acc, e) => acc + (e.capital_social ?? 0),
    0,
  );

  return (
    <aside
      key={selected.length}
      className="r-card r-slide-in sticky top-6 space-y-5 p-6"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="r-eyebrow">Seleção</p>
          <p className="r-display mt-1 text-2xl text-[var(--r-ink)]">
            {selected.length}{" "}
            {selected.length === 1 ? "fornecedor" : "fornecedores"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClear}
          aria-label="Limpar seleção"
          className="text-[var(--r-ink-3)] transition-colors hover:text-[var(--r-danger)]"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="rounded-xl bg-[var(--r-surface-2)] p-4">
        <p className="r-eyebrow mb-1.5">Capital somado</p>
        <p className="r-display text-xl text-[var(--r-ink)]">
          {formatBRL(totalCapital)}
        </p>
      </div>

      <ul className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
        {selected.map((e) => (
          <li
            key={e.cnpj_basico}
            className="group flex items-start justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-[var(--r-surface-2)]"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--r-ink)]">
                {e.nome_fantasia ?? e.razao_social}
              </p>
              <p className="r-mono truncate text-[10px] text-[var(--r-ink-3)]">
                {e.cnpj}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onRemove(e.cnpj_basico)}
              className="shrink-0 text-[var(--r-ink-3)] opacity-0 transition-opacity hover:text-[var(--r-danger)] group-hover:opacity-100"
              aria-label={`Remover ${e.razao_social} da seleção`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>

      <div className="space-y-2 border-t r-rule pt-4">
        <button
          type="button"
          onClick={async () => {
            setExporting(true);
            try {
              await apiDownload(
                `/api/v1/clusters/${clusterId}/shortlist.xlsx`,
                "shortlist.xlsx",
              );
            } finally {
              setExporting(false);
            }
          }}
          disabled={exporting}
          className="r-btn-primary w-full"
        >
          {exporting ? "Exportando…" : "Exportar shortlist (XLSX)"}
        </button>
        <p className="text-center text-[11px] text-[var(--r-ink-3)]">
          Export inclui toda a shortlist deste cluster · seleção é referência
          visual
        </p>
      </div>
    </aside>
  );
}
