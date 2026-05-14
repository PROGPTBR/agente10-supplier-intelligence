// frontend/app/uploads/[id]/page.tsx
"use client";

import { use, useState } from "react";
import { useClustersQuery } from "../../../lib/api/clusters";
import { useUploadStatusQuery } from "../../../lib/api/uploads";
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
  const [filters, setFilters] = useState<ClusterFilterState>({ search: "" });
  const done = upload.data?.status === "done";
  const clusters = useClustersQuery(
    id,
    { metodo: filters.metodo, revisado: filters.revisado },
    { enabled: done },
  );

  if (upload.isLoading)
    return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (upload.error || !upload.data) {
    return <p className="text-sm text-red-600">Upload não encontrado.</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Upload</h1>
      <UploadProgressBar
        status={upload.data.status}
        pct={upload.data.progresso_pct}
        erro={upload.data.erro}
      />
      {done && (
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
