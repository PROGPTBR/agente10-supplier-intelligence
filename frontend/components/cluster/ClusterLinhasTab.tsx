"use client";

import { useMemo, useState } from "react";
import {
  useClusterLinhasQuery,
  useClustersQuery,
  useMoveLinhasMutation,
} from "../../lib/api/clusters";
import type { ClusterSummary } from "../../lib/types";

const PAGE_SIZE = 50;

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

interface ClusterPickerProps {
  uploadId: string;
  excludeId: string;
  onPick: (cluster: ClusterSummary) => void;
  onClose: () => void;
}

function ClusterPicker({
  uploadId,
  excludeId,
  onPick,
  onClose,
}: ClusterPickerProps) {
  const [search, setSearch] = useState("");
  const clusters = useClustersQuery(uploadId, {}, { enabled: !!uploadId });

  const filtered = useMemo(() => {
    const all = clusters.data ?? [];
    const others = all.filter((c) => c.id !== excludeId);
    if (!search.trim()) return others.slice(0, 30);
    const q = search.toLowerCase();
    return others
      .filter((c) => {
        const name = (c.nome_cluster_refinado ?? c.nome_cluster).toLowerCase();
        return name.includes(q) || (c.cnae ?? "").includes(q);
      })
      .slice(0, 30);
  }, [clusters.data, search, excludeId]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Mover linhas para outro cluster"
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(14,10,43,0.4)] p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="r-card w-full max-w-lg p-5 r-slide-in"
      >
        <div className="mb-4 flex items-baseline justify-between">
          <p className="r-display text-lg text-[var(--r-ink)]">
            Mover linhas para…
          </p>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--r-ink-3)] hover:text-[var(--r-ink)]"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>
        <input
          type="search"
          autoFocus
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Pesquisar cluster por nome ou CNAE…"
          className="mb-3 w-full rounded-xl border bg-[var(--r-surface)] px-3.5 py-2.5 text-sm text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--r-primary-soft)]"
        />
        <ul
          role="listbox"
          className="max-h-80 overflow-y-auto rounded-xl border r-rule bg-[var(--r-surface)]"
        >
          {clusters.isLoading && (
            <li className="px-3 py-3 text-sm text-[var(--r-ink-2)]">
              Carregando clusters…
            </li>
          )}
          {filtered.length === 0 && !clusters.isLoading && (
            <li className="px-3 py-3 text-sm text-[var(--r-ink-2)]">
              Nenhum cluster encontrado.
            </li>
          )}
          {filtered.map((c) => {
            const label = c.nome_cluster_refinado ?? c.nome_cluster;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onPick(c)}
                  className="block w-full cursor-pointer px-3 py-2.5 text-left text-sm transition-colors hover:bg-[var(--r-surface-2)]"
                >
                  <div className="flex items-baseline gap-3">
                    <span className="truncate font-medium text-[var(--r-ink)]">
                      {label}
                    </span>
                    {c.cnae && (
                      <span className="r-mono ml-auto shrink-0 text-xs text-[var(--r-ink-2)]">
                        CNAE {c.cnae}
                      </span>
                    )}
                  </div>
                  <p className="r-mono mt-0.5 text-[10px] uppercase tracking-wider text-[var(--r-ink-3)]">
                    {c.num_linhas} linhas
                  </p>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

export function ClusterLinhasTab({
  clusterId,
  uploadId,
}: {
  clusterId: string;
  uploadId: string;
}) {
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: "ok" | "err";
    msg: string;
  } | null>(null);

  const linhas = useClusterLinhasQuery(clusterId, page, PAGE_SIZE);
  const move = useMoveLinhasMutation(clusterId);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (!linhas.data) return;
    const allOnPage = linhas.data.linhas.map((l) => l.id);
    const allSelected = allOnPage.every((id) => selected.has(id));
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        allOnPage.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        allOnPage.forEach((id) => next.add(id));
        return next;
      });
    }
  }

  function onPickTarget(target: ClusterSummary) {
    setPickerOpen(false);
    if (selected.size === 0) return;
    move.mutate(
      {
        linhaIds: Array.from(selected),
        targetClusterId: target.id,
      },
      {
        onSuccess: (data) => {
          setFeedback({
            kind: "ok",
            msg: `${data.moved} linha${data.moved === 1 ? "" : "s"} movida${
              data.moved === 1 ? "" : "s"
            } para "${target.nome_cluster_refinado ?? target.nome_cluster}".`,
          });
          setSelected(new Set());
        },
        onError: (e: Error) => setFeedback({ kind: "err", msg: e.message }),
      },
    );
  }

  if (linhas.isLoading)
    return <p className="text-sm text-[var(--r-ink-2)]">Carregando linhas…</p>;
  if (linhas.error || !linhas.data) {
    return (
      <p className="text-sm text-[var(--r-danger)]">Erro ao carregar linhas.</p>
    );
  }

  const totalPages = Math.max(1, Math.ceil(linhas.data.total / PAGE_SIZE));
  const allOnPageSelected =
    linhas.data.linhas.length > 0 &&
    linhas.data.linhas.every((l) => selected.has(l.id));
  const someOnPageSelected =
    !allOnPageSelected && linhas.data.linhas.some((l) => selected.has(l.id));

  return (
    <div className="space-y-5">
      {/* Action bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <p className="r-eyebrow">Linhas do cluster</p>
          <span className="r-mono text-xs text-[var(--r-ink-2)]">
            {linhas.data.total} total
          </span>
          {selected.size > 0 && (
            <span
              className="r-pill"
              style={{
                backgroundColor: "var(--r-primary-soft)",
                color: "var(--r-primary)",
              }}
            >
              {selected.size} selecionada
              {selected.size === 1 ? "" : "s"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              type="button"
              onClick={() => setSelected(new Set())}
              className="r-btn-ghost text-xs"
            >
              Limpar
            </button>
          )}
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={selected.size === 0 || move.isPending}
            className="r-btn-primary text-xs"
            title="Mover as linhas selecionadas para outro cluster do mesmo upload"
          >
            {move.isPending
              ? "Movendo…"
              : `Mover ${
                  selected.size > 0 ? `${selected.size} ` : ""
                }para outro cluster`}
          </button>
        </div>
      </div>

      {feedback && (
        <p
          className="text-xs"
          style={{
            color:
              feedback.kind === "ok" ? "var(--r-success)" : "var(--r-danger)",
          }}
        >
          {feedback.msg}
        </p>
      )}

      {/* Table */}
      <div className="r-card overflow-hidden">
        <table className="w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              <th scope="col" className="w-10 border-b r-rule px-3 py-3">
                <input
                  type="checkbox"
                  checked={allOnPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someOnPageSelected;
                  }}
                  onChange={toggleAll}
                  className="h-4 w-4 cursor-pointer rounded accent-[var(--r-primary)]"
                  aria-label="Selecionar todas da página"
                />
              </th>
              <th className="r-eyebrow border-b r-rule py-3 text-left">
                Descrição
              </th>
              <th className="r-eyebrow border-b r-rule py-3 text-left">
                Fornecedor atual
              </th>
              <th className="r-eyebrow border-b r-rule px-3 py-3 text-left">
                Valor
              </th>
            </tr>
          </thead>
          <tbody>
            {linhas.data.linhas.map((l) => {
              const isSel = selected.has(l.id);
              return (
                <tr
                  key={l.id}
                  onClick={() => toggle(l.id)}
                  className="r-hover-row cursor-pointer transition-colors"
                  style={
                    isSel
                      ? { backgroundColor: "var(--r-primary-soft)" }
                      : undefined
                  }
                >
                  <td className="border-b r-rule px-3 py-3">
                    <input
                      type="checkbox"
                      checked={isSel}
                      onClick={(ev) => ev.stopPropagation()}
                      onChange={() => toggle(l.id)}
                      className="h-4 w-4 cursor-pointer rounded accent-[var(--r-primary)]"
                      aria-label={`Selecionar linha ${l.descricao_original.slice(
                        0,
                        30,
                      )}`}
                    />
                  </td>
                  <td className="border-b r-rule py-3 text-[var(--r-ink)]">
                    {l.descricao_original}
                  </td>
                  <td className="border-b r-rule py-3 text-xs text-[var(--r-ink-2)]">
                    {l.fornecedor_atual ?? "—"}
                  </td>
                  <td className="r-mono border-b r-rule px-3 py-3 text-xs text-[var(--r-ink-2)]">
                    {formatBRL(l.valor_total)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-[var(--r-ink-2)]">
            Página {page + 1} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="r-btn-ghost text-xs"
            >
              ← Anterior
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="r-btn-ghost text-xs"
            >
              Próxima →
            </button>
          </div>
        </div>
      )}

      {pickerOpen && (
        <ClusterPicker
          uploadId={uploadId}
          excludeId={clusterId}
          onPick={onPickTarget}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}
