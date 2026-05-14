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
}: {
  clusterId: string;
  entries: ShortlistEntry[];
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        Nenhum fornecedor encontrado com os filtros atuais.
      </p>
    );
  }

  function toggle(cnpjBasico: string) {
    setExpanded((curr) => (curr === cnpjBasico ? null : cnpjBasico));
  }

  return (
    <table
      className="w-full border-separate border-spacing-0 text-sm"
      aria-label="Shortlist de fornecedores"
    >
      <thead className="text-left text-xs text-zinc-500">
        <tr>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            #
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Empresa
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            CNPJ (matriz)
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Filiais
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Capital
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            UF / Município
          </th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => {
          const isOpen = expanded === e.cnpj_basico;
          return (
            <Fragment key={e.cnpj_basico}>
              <tr
                onClick={() => toggle(e.cnpj_basico)}
                className="cursor-pointer hover:bg-zinc-50"
              >
                <td className="border-b border-zinc-100 py-2 text-zinc-500">
                  {e.rank_estagio3}
                </td>
                <td className="border-b border-zinc-100 py-2">
                  <span className="font-medium text-zinc-900">
                    {e.nome_fantasia ?? e.razao_social}
                  </span>
                  {e.nome_fantasia && (
                    <span className="block text-xs text-zinc-500">
                      {e.razao_social}
                    </span>
                  )}
                </td>
                <td className="border-b border-zinc-100 py-2 font-mono text-xs text-zinc-700">
                  {e.cnpj}
                </td>
                <td className="border-b border-zinc-100 py-2 text-zinc-700">
                  <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs">
                    {e.filiais_count}{" "}
                    {e.filiais_count === 1 ? "filial" : "filiais"}
                  </span>
                  <span className="ml-2 text-xs text-zinc-400">
                    {isOpen ? "▼" : "▶"}
                  </span>
                </td>
                <td className="border-b border-zinc-100 py-2 text-zinc-700">
                  {formatBRL(e.capital_social)}
                </td>
                <td className="border-b border-zinc-100 py-2 text-zinc-700">
                  {e.uf ?? "—"}
                  {e.municipio && (
                    <span className="block text-xs text-zinc-500">
                      {e.municipio}
                    </span>
                  )}
                </td>
              </tr>
              {isOpen && (
                <tr>
                  <td colSpan={6} className="border-b border-zinc-100">
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
