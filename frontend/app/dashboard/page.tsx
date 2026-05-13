"use client";

import { useDashboardStats } from "../../lib/api/dashboard";
import { StatCard } from "../../components/dashboard/StatCard";
import { ClustersByMetodoChart } from "../../components/dashboard/ClustersByMetodoChart";
import { RecentUploadsList } from "../../components/dashboard/RecentUploadsList";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardStats();

  if (isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (error || !data) {
    return <p className="text-sm text-red-600">Erro ao carregar dashboard.</p>;
  }

  const revisado_pct =
    data.clusters_total > 0
      ? (data.clusters_revised / data.clusters_total) * 100
      : 0;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Uploads totais" value={data.uploads_total} />
        <StatCard
          label="Uploads concluídos"
          value={data.uploads_done}
          sublabel={`${data.uploads_total - data.uploads_done} em andamento`}
        />
        <StatCard label="Clusters" value={data.clusters_total} />
        <StatCard
          label="Revisados"
          value={`${revisado_pct.toFixed(0)}%`}
          sublabel={`${data.clusters_revised} de ${data.clusters_total}`}
        />
      </div>
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <ClustersByMetodoChart data={data.clusters_by_metodo} />
      </div>
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Uploads recentes</h2>
        <RecentUploadsList uploads={data.recent_uploads} />
      </div>
    </div>
  );
}
