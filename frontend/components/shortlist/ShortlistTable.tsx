import type { ShortlistEntry } from "../../lib/types";

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function ShortlistTable({ entries }: { entries: ShortlistEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        Shortlist ainda não gerada — aguardando classificação CNAE do cluster.
      </p>
    );
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
            Razão social
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            CNPJ
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
        {entries.map((e) => (
          <tr key={e.cnpj}>
            <td className="border-b border-zinc-100 py-2 text-zinc-500">
              {e.rank_estagio3}
            </td>
            <td className="border-b border-zinc-100 py-2">
              <span className="font-medium text-zinc-900">
                {e.razao_social}
              </span>
              {e.nome_fantasia && (
                <span className="block text-xs text-zinc-500">
                  {e.nome_fantasia}
                </span>
              )}
            </td>
            <td className="border-b border-zinc-100 py-2 font-mono text-xs text-zinc-700">
              {e.cnpj}
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
        ))}
      </tbody>
    </table>
  );
}
