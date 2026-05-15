"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import {
  useClusterDetailQuery,
  useClustersQuery,
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
  const router = useRouter();
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
  const uploadId = cluster.data?.upload_id ?? "";
  const siblings = useClustersQuery(uploadId, {}, { enabled: !!uploadId });
  const orderedIds = siblings.data?.map((s) => s.id) ?? [];
  const currentIdx = orderedIds.indexOf(id);
  const prevId = currentIdx > 0 ? orderedIds[currentIdx - 1] : null;
  const nextId =
    currentIdx >= 0 && currentIdx < orderedIds.length - 1
      ? orderedIds[currentIdx + 1]
      : null;

  // Keyboard shortcuts: ← / → navigate between siblings (ignore when typing).
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
      <p className="r-serif text-xl italic text-[var(--r-ink-2)]">
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

  return (
    <div className="mx-auto max-w-6xl space-y-0">
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
        className="r-rise mt-5 flex flex-wrap items-end justify-between gap-6 border-b r-rule pb-8"
        style={{ animationDelay: "80ms" }}
      >
        <div className="min-w-0 max-w-3xl space-y-2">
          <p className="r-eyebrow">Categoria</p>
          <h1 className="r-serif text-4xl italic leading-tight tracking-tight text-[var(--r-ink)] sm:text-5xl">
            {displayName}
          </h1>
          {c.nome_cluster_refinado &&
            c.nome_cluster_refinado !== c.nome_cluster && (
              <p className="r-mono text-xs text-[var(--r-ink-3)]">
                bruto · {c.nome_cluster}
              </p>
            )}
          <p className="text-sm text-[var(--r-ink-2)]">
            <span className="r-mono text-[var(--r-ink)]">{c.num_linhas}</span>{" "}
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
            className="rounded-sm border border-[var(--r-rule)] bg-transparent px-3 py-1.5 text-sm text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-30"
          >
            ← Anterior
          </button>
          {currentIdx >= 0 && orderedIds.length > 0 && (
            <span className="r-mono text-xs uppercase tracking-wider text-[var(--r-ink-2)]">
              {currentIdx + 1} / {orderedIds.length}
            </span>
          )}
          <button
            type="button"
            onClick={() => nextId && router.push(`/clusters/${nextId}`)}
            disabled={!nextId}
            aria-label="Próximo cluster"
            title="Próximo cluster (→ seta direita)"
            className="rounded-sm border border-[var(--r-rule)] bg-transparent px-3 py-1.5 text-sm text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-30"
          >
            Próximo →
          </button>
        </div>
      </header>

      {/* Asymmetric body — 5/12 review, 7/12 sample + shortlist */}
      <div
        className="r-rise mt-10 grid grid-cols-1 gap-12 lg:grid-cols-12"
        style={{ animationDelay: "160ms" }}
      >
        {/* Left — review form */}
        <div className="lg:col-span-5 lg:border-r r-rule lg:pr-10">
          <ClusterReviewForm cluster={c} />
        </div>

        {/* Right — sample + meta */}
        <div className="space-y-10 lg:col-span-7">
          {c.sample_linhas.length > 0 && (
            <section className="space-y-3">
              <p className="r-eyebrow">Amostra das linhas</p>
              <ul className="space-y-1.5 border-l r-rule pl-4">
                {c.sample_linhas.map((s, i) => (
                  <li
                    key={i}
                    className="r-serif text-base italic leading-snug text-[var(--r-ink)]"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {c.notas_revisor && (
            <section className="space-y-3 border-t r-rule pt-8">
              <p className="r-eyebrow">Notas anteriores</p>
              <p className="text-sm leading-relaxed text-[var(--r-ink)] whitespace-pre-wrap">
                {c.notas_revisor}
              </p>
            </section>
          )}
        </div>
      </div>

      {/* Shortlist — full width */}
      <section
        className="r-rise mt-16 space-y-6 border-t r-rule pt-10"
        style={{ animationDelay: "320ms" }}
      >
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-1">
            <p className="r-eyebrow">Shortlist de fornecedores</p>
            <h2 className="r-serif text-2xl italic text-[var(--r-ink)]">
              {filtered ? "Resultado filtrado" : "Top por capital social"}
            </h2>
          </div>
          <div className="flex flex-wrap items-end gap-3">
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
              disabled={exporting || c.shortlist_gerada === false}
              className="rounded-sm border border-[var(--r-rule)] bg-transparent px-3.5 py-1.5 text-xs font-medium text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-40"
            >
              {exporting ? "Exportando…" : "Exportar XLSX"}
            </button>
          </div>
        </div>

        {c.shortlist_gerada === false && (
          <p className="r-mono text-xs uppercase tracking-wider text-[var(--r-warning)]">
            ● Regenerando shortlist…
          </p>
        )}
        {shortlist.isLoading && (
          <p className="text-sm text-[var(--r-ink-2)]">
            Carregando fornecedores…
          </p>
        )}
        {shortlist.data ? (
          <ShortlistTable clusterId={id} entries={shortlist.data} />
        ) : null}
      </section>
    </div>
  );
}
