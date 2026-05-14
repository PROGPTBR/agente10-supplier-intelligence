"use client";

import { useFiliaisQuery } from "../../lib/api/clusters";
import cnaeData from "../../lib/cnae-taxonomy.json";

interface CnaeRef {
  codigo: string;
  denominacao: string;
}

const CNAE_BY_CODE = new Map<string, string>(
  (cnaeData as CnaeRef[]).map((c) => [c.codigo, c.denominacao]),
);

function denomFor(code: string): string {
  return CNAE_BY_CODE.get(code) ?? "(descrição não encontrada)";
}

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

function CnaeList({
  primario,
  secundarios,
}: {
  primario: string | null;
  secundarios: string[];
}) {
  if (!primario && secundarios.length === 0) return <span>—</span>;
  return (
    <div className="space-y-0.5">
      {primario && (
        <div title={denomFor(primario)}>
          <span className="rounded bg-emerald-100 px-1 py-0.5 text-emerald-800">
            primário
          </span>{" "}
          <span className="font-mono">{primario}</span>{" "}
          <span className="text-zinc-500">— {denomFor(primario)}</span>
        </div>
      )}
      {secundarios.length > 0 && (
        <div className="flex flex-wrap items-baseline gap-1">
          <span className="text-zinc-500">secundários:</span>
          {secundarios.map((c) => (
            <span
              key={c}
              title={denomFor(c)}
              className="rounded bg-zinc-200 px-1 py-0.5 font-mono"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function FiliaisPanel({
  clusterId,
  cnpjBasico,
  empresaNome,
}: {
  clusterId: string;
  cnpjBasico: string | null;
  empresaNome: string | null;
}) {
  const filiais = useFiliaisQuery(clusterId, cnpjBasico);

  if (!cnpjBasico) return null;

  return (
    <div className="my-3 rounded border border-zinc-200 bg-zinc-50 p-3">
      <p className="mb-2 text-xs font-medium text-zinc-700">
        Filiais de {empresaNome ?? cnpjBasico}{" "}
        {filiais.data && (
          <span className="text-zinc-500">({filiais.data.length})</span>
        )}
      </p>
      {filiais.isLoading && (
        <p className="text-xs text-zinc-500">Carregando filiais…</p>
      )}
      {filiais.error && (
        <p className="text-xs text-red-600">Erro: {filiais.error.message}</p>
      )}
      {filiais.data && filiais.data.length === 0 && (
        <p className="text-xs text-zinc-500">Nenhuma filial encontrada.</p>
      )}
      {filiais.data && filiais.data.length > 0 && (
        <table className="w-full text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pb-1 text-left">Tipo</th>
              <th className="pb-1 text-left">CNPJ</th>
              <th className="pb-1 text-left">Razão / Fantasia</th>
              <th className="pb-1 text-left">UF / Município</th>
              <th className="pb-1 text-left">Capital</th>
              <th className="pb-1 text-left">Situação</th>
              <th className="pb-1 text-left">CNAEs</th>
            </tr>
          </thead>
          <tbody>
            {filiais.data.map((f) => (
              <tr key={f.cnpj} className="border-t border-zinc-200 align-top">
                <td className="py-1">
                  {f.is_matriz ? (
                    <span className="rounded bg-emerald-100 px-1 py-0.5 text-emerald-800">
                      Matriz
                    </span>
                  ) : (
                    <span className="text-zinc-500">Filial</span>
                  )}
                </td>
                <td className="py-1 font-mono">{f.cnpj}</td>
                <td className="py-1">
                  {f.razao_social}
                  {f.nome_fantasia && (
                    <span className="block text-zinc-500">
                      {f.nome_fantasia}
                    </span>
                  )}
                </td>
                <td className="py-1 text-zinc-700">
                  {f.uf ?? "—"}
                  {f.municipio && (
                    <span className="block text-zinc-500">{f.municipio}</span>
                  )}
                </td>
                <td className="py-1 text-zinc-700">
                  {formatBRL(f.capital_social)}
                </td>
                <td className="py-1 text-zinc-700">
                  {f.situacao_cadastral ?? "—"}
                </td>
                <td className="py-1 text-zinc-700">
                  <CnaeList
                    primario={f.cnae_primario}
                    secundarios={f.cnaes_secundarios}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
