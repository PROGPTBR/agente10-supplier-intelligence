"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import {
  useClusterDetailQuery,
  useClustersQuery,
  useShortlistQuery,
} from "../../../lib/api/clusters";
import { ClusterReviewForm } from "../../../components/cluster/ClusterReviewForm";
import { ClusterLinhasTab } from "../../../components/cluster/ClusterLinhasTab";
import { ShortlistTable } from "../../../components/shortlist/ShortlistTable";
import {
  ShortlistFilters,
  type ShortlistFilterState,
} from "../../../components/shortlist/ShortlistFilters";
import { SelectionPanel } from "../../../components/shortlist/SelectionPanel";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../../components/ui/tabs";

export default function ClusterDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const cluster = useClusterDetailQuery(id);
  const [filters, setFilters] = useState<ShortlistFilterState>({
    uf: "",
    municipio: "",
  });
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  // Reset selection when navigating to a different cluster — state-during-render
  // pattern (https://react.dev/reference/react/useState#storing-information-from-previous-renders)
  // avoids the cascading re-render an effect would trigger.
  const [lastClusterId, setLastClusterId] = useState(id);
  if (lastClusterId !== id) {
    setLastClusterId(id);
    setSelectedKeys(new Set());
  }
  const shortlist = useShortlistQuery(id, cluster.data?.shortlist_gerada, {
    uf: filters.uf || undefined,
    municipio: filters.municipio || undefined,
  });
  const uploadId = cluster.data?.upload_id ?? "";
  const siblings = useClustersQuery(uploadId, {}, { enabled: !!uploadId });
  const orderedIds = siblings.data?.map((s) => s.id) ?? [];
  const currentIdx = orderedIds.indexOf(id);
  const prevId = currentIdx > 0 ? orderedIds[currentIdx - 1] : null;
  const nextId =
    currentIdx >= 0 && currentIdx < orderedIds.length - 1
      ? orderedIds[currentIdx + 1]
      : null;

  // Keyboard shortcuts: ← / → navigate between siblings
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const isEditable =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (isEditable) return;
      if (e.key === "ArrowLeft" && prevId) router.push(`/clusters/${prevId}`);
      if (e.key === "ArrowRight" && nextId) router.push(`/clusters/${nextId}`);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prevId, nextId, router]);

  if (cluster.isLoading)
    return (
      <p className="r-display text-xl text-[var(--r-ink-2)]">
        Carregando cluster…
      </p>
    );
  if (cluster.error || !cluster.data) {
    return (
      <p className="text-sm text-[var(--r-danger)]">Cluster não encontrado.</p>
    );
  }

  const c = cluster.data;
  const filtered = !!(filters.uf || filters.municipio);
  const displayName = c.nome_cluster_refinado ?? c.nome_cluster;

  function toggleSelect(cnpjBasico: string) {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(cnpjBasico)) next.delete(cnpjBasico);
      else next.add(cnpjBasico);
      return next;
    });
  }

  function toggleSelectAll() {
    if (!shortlist.data) return;
    const allKeys = shortlist.data.map((e) => e.cnpj_basico);
    const allSelected = allKeys.every((k) => selectedKeys.has(k));
    if (allSelected) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(allKeys));
    }
  }

  const selectedEntries = (shortlist.data ?? []).filter((e) =>
    selectedKeys.has(e.cnpj_basico),
  );

  return (
    <div className="mx-auto max-w-7xl">
      {/* Breadcrumb */}
      <nav className="r-eyebrow r-rise flex items-center gap-2">
        <Link
          href={`/relatorios/${c.upload_id}`}
          className="hover:text-[var(--r-ink)] transition-colors"
        >
          ← Relatório
        </Link>
        <span aria-hidden>›</span>
        <span className="text-[var(--r-ink)]">Cluster</span>
      </nav>

      {/* Title row */}
      <header
        className="r-rise mt-5 flex flex-wrap items-end justify-between gap-6"
        style={{ animationDelay: "60ms" }}
      >
        <div className="min-w-0 max-w-3xl space-y-2">
          <p className="r-eyebrow">Categoria</p>
          <h1 className="r-display text-3xl leading-tight tracking-tight text-[var(--r-ink)] sm:text-4xl">
            {displayName}
          </h1>
          {c.nome_cluster_refinado &&
            c.nome_cluster_refinado !== c.nome_cluster && (
              <p className="r-mono text-xs text-[var(--r-ink-3)]">
                bruto · {c.nome_cluster}
              </p>
            )}
          <p className="text-sm text-[var(--r-ink-2)]">
            <span className="r-mono font-semibold text-[var(--r-ink)]">
              {c.num_linhas}
            </span>{" "}
            {c.num_linhas === 1 ? "linha" : "linhas"} agrupadas
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => prevId && router.push(`/clusters/${prevId}`)}
            disabled={!prevId}
            aria-label="Cluster anterior"
            title="Cluster anterior (← seta esquerda)"
            className="r-btn-ghost"
          >
            ← Anterior
          </button>
          {currentIdx >= 0 && orderedIds.length > 0 && (
            <span className="r-mono px-2 text-xs uppercase tracking-wider text-[var(--r-ink-2)]">
              {currentIdx + 1} / {orderedIds.length}
            </span>
          )}
          <button
            type="button"
            onClick={() => nextId && router.push(`/clusters/${nextId}`)}
            disabled={!nextId}
            aria-label="Próximo cluster"
            title="Próximo cluster (→ seta direita)"
            className="r-btn-ghost"
          >
            Próximo →
          </button>
        </div>
      </header>

      {/* Tabs */}
      <section className="r-rise mt-10" style={{ animationDelay: "160ms" }}>
        <Tabs defaultValue="review" className="w-full">
          <TabsList>
            <TabsTrigger value="review">Revisão CNAE</TabsTrigger>
            <TabsTrigger value="linhas">Linhas</TabsTrigger>
            <TabsTrigger value="shortlist">Shortlist</TabsTrigger>
          </TabsList>

          {/* TAB: Revisão CNAE (review form + sample lines) */}
          <TabsContent value="review">
            <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
              <div className="lg:col-span-7">
                <ClusterReviewForm cluster={c} />
              </div>
              <div className="space-y-8 lg:col-span-5">
                {c.sample_linhas.length > 0 && (
                  <section className="r-card p-6">
                    <p className="r-eyebrow mb-3">Amostra das linhas</p>
                    <ul className="space-y-2">
                      {c.sample_linhas.map((s, i) => (
                        <li
                          key={i}
                          className="rounded-lg bg-[var(--r-surface-2)] px-3 py-2 text-sm leading-snug text-[var(--r-ink)]"
                        >
                          {s}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {c.notas_revisor && (
                  <section className="r-card space-y-3 p-6">
                    <p className="r-eyebrow">Notas anteriores</p>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--r-ink)]">
                      {c.notas_revisor}
                    </p>
                  </section>
                )}
              </div>
            </div>
          </TabsContent>

          {/* TAB: Linhas (full list + multi-select + move) */}
          <TabsContent value="linhas">
            <ClusterLinhasTab clusterId={id} uploadId={c.upload_id} />
          </TabsContent>

          {/* TAB: Shortlist */}
          <TabsContent value="shortlist">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="r-eyebrow">Shortlist de fornecedores</p>
                <h2 className="r-display mt-1 text-2xl text-[var(--r-ink)]">
                  {filtered ? "Resultado filtrado" : "Top por capital social"}
                </h2>
              </div>
              <ShortlistFilters value={filters} onChange={setFilters} />
            </div>

            {c.shortlist_gerada === false && (
              <p
                className="r-pill mb-4"
                style={{
                  backgroundColor: "rgba(245,158,11,0.14)",
                  color: "#B45309",
                }}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: "#F59E0B" }}
                />
                Regenerando shortlist…
              </p>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
              <div className="r-card overflow-hidden">
                {shortlist.isLoading && (
                  <p className="p-6 text-sm text-[var(--r-ink-2)]">
                    Carregando fornecedores…
                  </p>
                )}
                {shortlist.data && (
                  <ShortlistTable
                    clusterId={id}
                    entries={shortlist.data}
                    selectedKeys={selectedKeys}
                    onToggleSelect={toggleSelect}
                    onToggleSelectAll={toggleSelectAll}
                  />
                )}
              </div>

              <div className="lg:sticky lg:top-6 lg:self-start">
                {selectedEntries.length === 0 ? (
                  <div className="r-card p-6 text-center">
                    <div
                      aria-hidden
                      className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full"
                      style={{ backgroundColor: "var(--r-primary-soft)" }}
                    >
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--r-primary)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <p className="r-display text-base text-[var(--r-ink)]">
                      Marque fornecedores
                    </p>
                    <p className="mt-1.5 text-xs text-[var(--r-ink-2)]">
                      Selecione com as checkboxes para ver totais e ações
                    </p>
                  </div>
                ) : (
                  <SelectionPanel
                    clusterId={id}
                    selected={selectedEntries}
                    onClear={() => setSelectedKeys(new Set())}
                    onRemove={toggleSelect}
                  />
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </section>
    </div>
  );
}
