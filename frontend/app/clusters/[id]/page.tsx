"use client";

import Link from "next/link";
import { use, useState } from "react";
import {
  useClusterDetailQuery,
  useShortlistQuery,
} from "../../../lib/api/clusters";
import { apiDownload } from "../../../lib/api/client";
import { ClusterReviewForm } from "../../../components/cluster/ClusterReviewForm";
import { ShortlistTable } from "../../../components/shortlist/ShortlistTable";
import {
  ShortlistFilters,
  type ShortlistFilterState,
} from "../../../components/shortlist/ShortlistFilters";

export default function ClusterDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const cluster = useClusterDetailQuery(id);
  const [filters, setFilters] = useState<ShortlistFilterState>({
    uf: "",
    municipio: "",
  });
  const [exporting, setExporting] = useState(false);
  const shortlist = useShortlistQuery(id, cluster.data?.shortlist_gerada, {
    uf: filters.uf || undefined,
    municipio: filters.municipio || undefined,
  });

  if (cluster.isLoading)
    return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (cluster.error || !cluster.data) {
    return <p className="text-sm text-red-600">Cluster não encontrado.</p>;
  }
  return (
    <div className="space-y-8">
      <div>
        <Link
          href={`/uploads/${cluster.data.upload_id}`}
          className="text-sm text-zinc-500 hover:underline"
        >
          ← Voltar ao upload
        </Link>
      </div>
      <ClusterReviewForm cluster={cluster.data} />
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-medium">
            Shortlist de fornecedores
            {filters.uf || filters.municipio
              ? " (filtrado)"
              : " (top 10 por capital)"}
          </h2>
          <div className="flex items-end gap-3">
            <ShortlistFilters value={filters} onChange={setFilters} />
            <button
              type="button"
              onClick={async () => {
                setExporting(true);
                try {
                  await apiDownload(
                    `/api/v1/clusters/${id}/shortlist.xlsx`,
                    "shortlist.xlsx",
                  );
                } finally {
                  setExporting(false);
                }
              }}
              disabled={exporting || cluster.data.shortlist_gerada === false}
              className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              title="Baixa a shortlist deste cluster em XLSX"
            >
              {exporting ? "Exportando…" : "Exportar XLSX"}
            </button>
          </div>
        </div>
        {cluster.data.shortlist_gerada === false && (
          <p className="text-xs text-amber-700">Regenerando shortlist…</p>
        )}
        {shortlist.isLoading && (
          <p className="text-xs text-zinc-500">Carregando fornecedores…</p>
        )}
        {shortlist.data ? (
          <ShortlistTable clusterId={id} entries={shortlist.data} />
        ) : null}
      </section>
    </div>
  );
}
