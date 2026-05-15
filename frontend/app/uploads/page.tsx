"use client";

import Link from "next/link";
import {
  useDeleteUploadMutation,
  useRetryUploadMutation,
  useUploadsQuery,
} from "../../lib/api/uploads";
import { formatDuration } from "../../lib/format";

const STATUS_STYLE: Record<string, { label: string; bg: string; fg: string }> =
  {
    done: { label: "Concluído", bg: "rgba(16,185,129,0.12)", fg: "#047857" },
    processing: {
      label: "Processando",
      bg: "rgba(91,63,229,0.12)",
      fg: "var(--r-primary)",
    },
    pending: {
      label: "Aguardando",
      bg: "var(--r-surface-2)",
      fg: "var(--r-ink-2)",
    },
    failed: { label: "Falhou", bg: "rgba(239,68,68,0.12)", fg: "#B91C1C" },
  };

export default function UploadsListPage() {
  const { data, isLoading, error } = useUploadsQuery();
  const retry = useRetryUploadMutation();
  const del = useDeleteUploadMutation();

  function onRetry(uploadId: string) {
    retry.mutate(uploadId);
  }

  function onDelete(uploadId: string, nome: string) {
    if (confirm(`Apagar definitivamente o upload "${nome}"?`)) {
      del.mutate(uploadId);
    }
  }

  if (isLoading)
    return (
      <p className="r-display text-xl text-[var(--r-ink-2)]">
        Carregando relatórios…
      </p>
    );
  if (error || !data) {
    return (
      <p className="text-sm text-[var(--r-danger)]">
        Erro ao carregar relatórios.
      </p>
    );
  }
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="r-rise flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="r-eyebrow">Relatórios</p>
          <h1 className="r-display text-4xl text-[var(--r-ink)]">
            Análises de fornecedores
          </h1>
          <p className="text-sm text-[var(--r-ink-2)]">
            Cada arquivo enviado gera um relatório com clusters classificados e
            shortlist de fornecedores.
          </p>
        </div>
        <Link href="/uploads/new" className="r-btn-primary">
          + Novo relatório
        </Link>
      </header>

      {data.length === 0 ? (
        <div
          className="r-card r-rise flex flex-col items-center gap-3 py-16 text-center"
          style={{ animationDelay: "80ms" }}
        >
          <div
            aria-hidden
            className="flex h-12 w-12 items-center justify-center rounded-full"
            style={{ backgroundColor: "var(--r-primary-soft)" }}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--r-primary)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
              <polyline points="14 3 14 8 19 8" />
            </svg>
          </div>
          <p className="r-display text-lg text-[var(--r-ink)]">
            Nenhum relatório ainda
          </p>
          <p className="text-sm text-[var(--r-ink-2)]">
            Comece subindo um CSV de catálogo.
          </p>
          <Link href="/uploads/new" className="r-btn-primary mt-2">
            Subir primeiro arquivo
          </Link>
        </div>
      ) : (
        <div
          className="r-card r-rise overflow-hidden"
          style={{ animationDelay: "80ms" }}
        >
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="r-eyebrow border-b r-rule px-5 py-4 text-left">
                  Arquivo
                </th>
                <th className="r-eyebrow border-b r-rule py-4 text-left">
                  Status
                </th>
                <th className="r-eyebrow border-b r-rule py-4 text-left">
                  Linhas
                </th>
                <th className="r-eyebrow border-b r-rule py-4 text-left">
                  Progresso
                </th>
                <th className="r-eyebrow border-b r-rule py-4 text-left">
                  Duração
                </th>
                <th className="r-eyebrow border-b r-rule py-4 text-left">
                  Enviado
                </th>
                <th className="r-eyebrow border-b r-rule px-5 py-4 text-right">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((u) => {
                const s = STATUS_STYLE[u.status] ?? STATUS_STYLE.pending;
                return (
                  <tr
                    key={u.upload_id}
                    className="r-hover-row transition-colors"
                  >
                    <td className="border-b r-rule px-5 py-4">
                      <Link
                        href={`/relatorios/${u.upload_id}`}
                        className="font-medium text-[var(--r-ink)] transition-colors hover:text-[var(--r-primary)]"
                      >
                        {u.nome_arquivo}
                      </Link>
                    </td>
                    <td className="border-b r-rule py-4">
                      <span
                        className="r-pill"
                        style={{ backgroundColor: s.bg, color: s.fg }}
                      >
                        {s.label}
                      </span>
                    </td>
                    <td className="r-mono border-b r-rule py-4 text-xs text-[var(--r-ink)]">
                      {u.linhas_classificadas}/{u.linhas_total}
                    </td>
                    <td className="border-b r-rule py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-[var(--r-surface-2)]">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.min(100, u.progresso_pct)}%`,
                              background:
                                "linear-gradient(90deg, #8C84FF, #5B3FE5)",
                            }}
                          />
                        </div>
                        <span className="r-mono text-xs text-[var(--r-ink-2)]">
                          {u.progresso_pct.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="r-mono border-b r-rule py-4 text-xs text-[var(--r-ink-2)]">
                      {formatDuration(u.duracao_segundos)}
                    </td>
                    <td className="border-b r-rule py-4 text-xs text-[var(--r-ink-2)]">
                      {new Date(u.data_upload).toLocaleString("pt-BR")}
                    </td>
                    <td className="border-b r-rule px-5 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => onRetry(u.upload_id)}
                          disabled={retry.isPending}
                          className="r-btn-ghost text-xs"
                          title="Reprocessar"
                        >
                          Retry
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(u.upload_id, u.nome_arquivo)}
                          disabled={del.isPending}
                          className="rounded-lg border border-transparent px-3 py-1.5 text-xs font-medium text-[var(--r-danger)] transition-colors hover:bg-[rgba(239,68,68,0.08)] hover:border-[rgba(239,68,68,0.2)] disabled:opacity-40"
                          title="Apagar relatório"
                        >
                          Apagar
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
