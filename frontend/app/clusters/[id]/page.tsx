"use client";

import Link from "next/link";
import { use } from "react";
import {
  useClusterDetailQuery,
  useShortlistQuery,
} from "../../../lib/api/clusters";
import { ClusterReviewForm } from "../../../components/cluster/ClusterReviewForm";
import { ShortlistTable } from "../../../components/shortlist/ShortlistTable";

export default function ClusterDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const cluster = useClusterDetailQuery(id);
  const shortlist = useShortlistQuery(id, cluster.data?.shortlist_gerada);

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
        <h2 className="text-lg font-medium">
          Shortlist de fornecedores (top 10)
        </h2>
        {cluster.data.shortlist_gerada === false && (
          <p className="text-xs text-amber-700">Regenerando shortlist…</p>
        )}
        {shortlist.data ? <ShortlistTable entries={shortlist.data} /> : null}
      </section>
    </div>
  );
}
