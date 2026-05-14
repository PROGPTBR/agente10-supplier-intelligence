// frontend/components/cluster/ClusterTable.tsx
import Link from "next/link";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { ClusterSummary } from "../../lib/types";

export function ClusterTable({
  clusters,
  searchTerm,
}: {
  clusters: ClusterSummary[];
  searchTerm: string;
}) {
  const filtered = searchTerm.trim()
    ? clusters.filter((c) => {
        const haystack = c.nome_cluster + " " + (c.nome_cluster_refinado ?? "");
        return haystack.toLowerCase().includes(searchTerm.toLowerCase());
      })
    : clusters;

  if (filtered.length === 0) {
    return <p className="text-sm text-zinc-500">Nenhum cluster encontrado.</p>;
  }
  return (
    <table
      className="w-full border-separate border-spacing-0 text-sm"
      aria-label="Clusters"
    >
      <thead className="text-left text-xs text-zinc-500">
        <tr>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Cluster
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Linhas
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            CNAE
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Método
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Revisado
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2">
            Shortlist
          </th>
          <th scope="col" className="border-b border-zinc-200 pb-2" />
        </tr>
      </thead>
      <tbody>
        {filtered.map((c) => (
          <tr key={c.id} className="hover:bg-zinc-50">
            <td className="border-b border-zinc-100 py-3 font-medium text-zinc-900">
              {c.nome_cluster_refinado ?? c.nome_cluster}
              {c.nome_cluster_refinado &&
                c.nome_cluster_refinado !== c.nome_cluster && (
                  <span className="block text-xs font-normal text-zinc-500">
                    bruto: {c.nome_cluster}
                  </span>
                )}
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.num_linhas}
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.cnae ?? "—"}
              {c.cnae_descricao && (
                <span className="block text-xs text-zinc-500">
                  {c.cnae_descricao}
                </span>
              )}
              {c.cnaes_secundarios.length > 0 && (
                <span className="mt-1 block text-xs text-zinc-500">
                  + {c.cnaes_secundarios.join(", ")}
                </span>
              )}
            </td>
            <td className="border-b border-zinc-100 py-3">
              <ConfidenceBadge
                metodo={c.cnae_metodo}
                confianca={c.cnae_confianca}
              />
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.revisado_humano ? "✓" : "—"}
            </td>
            <td className="border-b border-zinc-100 py-3 text-zinc-700">
              {c.shortlist_size}
            </td>
            <td className="border-b border-zinc-100 py-3 text-right">
              <Link
                href={`/clusters/${c.id}`}
                className="text-sm font-medium text-zinc-900 hover:underline"
              >
                Abrir →
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
