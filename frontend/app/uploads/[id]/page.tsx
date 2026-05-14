// frontend/app/uploads/[id]/page.tsx
"use client";

import { use, useState } from "react";
import { useClustersQuery } from "../../../lib/api/clusters";
import { apiDownload } from "../../../lib/api/client";
import {
  useRetryUploadMutation,
  useUploadStatusQuery,
} from "../../../lib/api/uploads";
import {
  ClusterFilters,
  type ClusterFilterState,
} from "../../../components/cluster/ClusterFilters";
import { ClusterTable } from "../../../components/cluster/ClusterTable";
import { UploadProgressBar } from "../../../components/upload/UploadProgressBar";

export default function UploadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const upload = useUploadStatusQuery(id);
  const retry = useRetryUploadMutation();
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState<ClusterFilterState>({ search: "" });
  // Show clusters as soon as classification is complete (linhas_classificadas
  // reached linhas_total). Shortlist stage may still be running in background
  // but the cluster table itself is already meaningful.
  const classificationDone =
    upload.data !== undefined &&
    upload.data.linhas_total > 0 &&
    upload.data.linhas_classificadas >= upload.data.linhas_total;
  const clusters = useClustersQuery(
    id,
    { metodo: filters.metodo, revisado: filters.revisado },
    { enabled: classificationDone },
  );

  if (upload.isLoading)
    return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (upload.error || !upload.data) {
    return <p className="text-sm text-red-600">Upload não encontrado.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Upload</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={async () => {
              setExporting(true);
              try {
                await apiDownload(
                  `/api/v1/uploads/${id}/shortlist.xlsx`,
                  "shortlist.xlsx",
                );
              } finally {
                setExporting(false);
              }
            }}
            disabled={exporting || !classificationDone}
            className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
            title="Baixa a shortlist consolidada de todos os clusters em XLSX"
          >
            {exporting ? "Exportando…" : "Exportar XLSX"}
          </button>
          <button
            type="button"
            onClick={() => retry.mutate(id)}
            disabled={retry.isPending || upload.data.status === "pending"}
            className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
            title="Reprocessa o upload (reaplica consolidação e shortlist)"
          >
            {retry.isPending ? "Reenviando…" : "Reprocessar"}
          </button>
        </div>
      </div>
      <UploadProgressBar
        status={upload.data.status}
        pct={upload.data.progresso_pct}
        erro={upload.data.erro}
        clustersTotal={upload.data.clusters_total}
        clustersClassificados={upload.data.clusters_classificados}
        clustersComShortlist={upload.data.clusters_com_shortlist}
        duracaoSegundos={upload.data.duracao_segundos}
      />
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-zinc-500">Configuração da shortlist:</span>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">
          Top {upload.data.shortlist_config.size}
        </span>
        {upload.data.shortlist_config.uf && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-700">
            UF: {upload.data.shortlist_config.uf}
          </span>
        )}
        {upload.data.shortlist_config.municipio && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-700">
            Município: {upload.data.shortlist_config.municipio}
          </span>
        )}
        {upload.data.shortlist_config.only_matriz && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-700">
            Apenas matriz
          </span>
        )}
        {upload.data.shortlist_config.min_capital !== null && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-700">
            Capital ≥{" "}
            {upload.data.shortlist_config.min_capital.toLocaleString("pt-BR", {
              style: "currency",
              currency: "BRL",
              maximumFractionDigits: 0,
            })}
          </span>
        )}
      </div>
      {classificationDone && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Clusters</h2>
          <ClusterFilters value={filters} onChange={setFilters} />
          {clusters.isLoading && (
            <p className="text-sm text-zinc-500">Carregando clusters…</p>
          )}
          {clusters.data && (
            <ClusterTable
              clusters={clusters.data}
              searchTerm={filters.search}
            />
          )}
        </div>
      )}
    </div>
  );
}
