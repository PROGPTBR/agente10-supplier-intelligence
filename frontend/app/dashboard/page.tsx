"use client";

import { useDashboardStats } from "../../lib/api/dashboard";
import { StatCard } from "../../components/dashboard/StatCard";
import { ClustersByMetodoChart } from "../../components/dashboard/ClustersByMetodoChart";
import { RecentUploadsList } from "../../components/dashboard/RecentUploadsList";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardStats();

  if (isLoading)
    return (
      <p className="r-display text-xl text-[var(--r-ink-2)]">
        Carregando dashboard…
      </p>
    );
  if (error || !data) {
    return (
      <p className="text-sm text-[var(--r-danger)]">
        Erro ao carregar dashboard.
      </p>
    );
  }

  const revisado_pct =
    data.clusters_total > 0
      ? (data.clusters_revised / data.clusters_total) * 100
      : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="r-rise space-y-2">
        <p className="r-eyebrow">Painel geral</p>
        <h1 className="r-display text-4xl text-[var(--r-ink)]">Dashboard</h1>
      </header>
      <div
        className="r-rise grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        style={{ animationDelay: "80ms" }}
      >
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
      <div className="r-card r-rise p-7" style={{ animationDelay: "160ms" }}>
        <ClustersByMetodoChart data={data.clusters_by_metodo} />
      </div>
      <div className="r-card r-rise p-7" style={{ animationDelay: "240ms" }}>
        <p className="r-eyebrow mb-4">Uploads recentes</p>
        <RecentUploadsList uploads={data.recent_uploads} />
      </div>
    </div>
  );
}
