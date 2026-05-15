"use client";

import { Fragment, useState } from "react";
import type { ShortlistEntry } from "../../lib/types";
import { FiliaisPanel } from "./FiliaisPanel";

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function ShortlistTable({
  clusterId,
  entries,
  selectedKeys,
  onToggleSelect,
  onToggleSelectAll,
}: {
  clusterId: string;
  entries: ShortlistEntry[];
  selectedKeys?: Set<string>;
  onToggleSelect?: (cnpjBasico: string) => void;
  onToggleSelectAll?: () => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (entries.length === 0) {
    return (
      <p className="r-display text-base text-[var(--r-ink-2)]">
        Nenhum fornecedor encontrado com os filtros atuais.
      </p>
    );
  }

  function toggle(cnpjBasico: string) {
    setExpanded((curr) => (curr === cnpjBasico ? null : cnpjBasico));
  }

  const showCheckboxes = !!onToggleSelect && !!selectedKeys;
  const allSelected =
    showCheckboxes && entries.every((e) => selectedKeys!.has(e.cnpj_basico));
  const someSelected =
    showCheckboxes &&
    !allSelected &&
    entries.some((e) => selectedKeys!.has(e.cnpj_basico));

  return (
    <table
      className="w-full border-separate border-spacing-0 text-sm"
      aria-label="Shortlist de fornecedores"
    >
      <thead>
        <tr>
          {showCheckboxes && (
            <th scope="col" className="w-10 border-b r-rule px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected;
                }}
                onChange={onToggleSelectAll}
                className="h-4 w-4 cursor-pointer rounded accent-[var(--r-primary)]"
                aria-label="Selecionar todos"
              />
            </th>
          )}
          <th
            scope="col"
            className="r-eyebrow border-b r-rule px-3 py-3 text-left"
          >
            #
          </th>
          <th scope="col" className="r-eyebrow border-b r-rule py-3 text-left">
            Empresa
          </th>
          <th scope="col" className="r-eyebrow border-b r-rule py-3 text-left">
            CNPJ (matriz)
          </th>
          <th scope="col" className="r-eyebrow border-b r-rule py-3 text-left">
            Filiais
          </th>
          <th scope="col" className="r-eyebrow border-b r-rule py-3 text-left">
            Capital
          </th>
          <th
            scope="col"
            className="r-eyebrow border-b r-rule px-3 py-3 text-left"
          >
            UF / Município
          </th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => {
          const isOpen = expanded === e.cnpj_basico;
          const isSelected = showCheckboxes && selectedKeys!.has(e.cnpj_basico);
          return (
            <Fragment key={e.cnpj_basico}>
              <tr
                onClick={() => toggle(e.cnpj_basico)}
                className="r-hover-row cursor-pointer transition-colors"
                style={
                  isSelected
                    ? { backgroundColor: "var(--r-primary-soft)" }
                    : undefined
                }
              >
                {showCheckboxes && (
                  <td className="border-b r-rule px-3 py-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onClick={(ev) => ev.stopPropagation()}
                      onChange={() => onToggleSelect!(e.cnpj_basico)}
                      className="h-4 w-4 cursor-pointer rounded accent-[var(--r-primary)]"
                      aria-label={`Selecionar ${e.razao_social}`}
                    />
                  </td>
                )}
                <td className="r-mono border-b r-rule px-3 py-3 text-xs text-[var(--r-ink-3)]">
                  {String(e.rank_estagio3).padStart(2, "0")}
                </td>
                <td className="border-b r-rule py-3">
                  <span className="font-medium text-[var(--r-ink)]">
                    {e.nome_fantasia ?? e.razao_social}
                  </span>
                  {e.nome_fantasia && (
                    <span className="block text-xs text-[var(--r-ink-2)]">
                      {e.razao_social}
                    </span>
                  )}
                </td>
                <td className="r-mono border-b r-rule py-3 text-xs text-[var(--r-ink)]">
                  {e.cnpj}
                </td>
                <td className="border-b r-rule py-3 text-[var(--r-ink-2)]">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="r-mono font-semibold text-[var(--r-ink)]">
                      {e.filiais_count}
                    </span>
                    <span className="text-xs">
                      {e.filiais_count === 1 ? "filial" : "filiais"}
                    </span>
                  </span>
                  <span className="ml-2 text-[10px] text-[var(--r-ink-3)]">
                    {isOpen ? "▼" : "▶"}
                  </span>
                </td>
                <td className="r-mono border-b r-rule py-3 text-xs text-[var(--r-ink)]">
                  {formatBRL(e.capital_social)}
                </td>
                <td className="border-b r-rule px-3 py-3 text-[var(--r-ink-2)]">
                  <span className="r-mono font-semibold text-[var(--r-ink)]">
                    {e.uf ?? "—"}
                  </span>
                  {e.municipio && (
                    <span className="block text-xs text-[var(--r-ink-2)]">
                      {e.municipio}
                    </span>
                  )}
                </td>
              </tr>
              {isOpen && (
                <tr>
                  <td
                    colSpan={showCheckboxes ? 7 : 6}
                    className="border-b r-rule"
                  >
                    <FiliaisPanel
                      clusterId={clusterId}
                      cnpjBasico={e.cnpj_basico}
                      empresaNome={e.nome_fantasia ?? e.razao_social}
                    />
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
