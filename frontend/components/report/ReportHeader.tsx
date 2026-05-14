"use client";

import Link from "next/link";
import { useState } from "react";
import { apiDownload } from "../../lib/api/client";
import type { UploadStatus } from "../../lib/types";

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  done: { label: "Concluído", color: "var(--r-success)" },
  processing: { label: "Processando", color: "#0e7490" },
  pending: { label: "Aguardando", color: "var(--r-ink-2)" },
  failed: { label: "Falhou", color: "var(--r-danger)" },
};

function formatDuration(seconds: number | null): string | null {
  if (seconds === null) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function ReportHeader({
  upload,
  filename,
  onRetry,
  retryPending,
}: {
  upload: UploadStatus;
  filename: string;
  onRetry: () => void;
  retryPending: boolean;
}) {
  const [exporting, setExporting] = useState(false);
  const status = STATUS_LABEL[upload.status] ?? STATUS_LABEL.pending;
  const dur = formatDuration(upload.duracao_segundos);
  const canExport =
    upload.linhas_total > 0 &&
    upload.linhas_classificadas >= upload.linhas_total;

  return (
    <header className="r-rise space-y-5">
      <nav className="r-eyebrow flex items-center gap-2">
        <Link
          href="/uploads"
          className="hover:text-[var(--r-ink)] transition-colors"
        >
          Relatórios
        </Link>
        <span aria-hidden>›</span>
        <span className="text-[var(--r-ink)]">{filename}</span>
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-6 border-b r-rule pb-6">
        <div className="space-y-2">
          <h1 className="r-serif text-4xl italic leading-none tracking-tight text-[var(--r-ink)] sm:text-5xl">
            {filename.replace(/\.(csv|xlsx)$/i, "")}
          </h1>
          <div className="flex items-center gap-3 text-sm">
            <span
              className="inline-flex items-center gap-1.5"
              style={{ color: status.color }}
            >
              <span
                aria-hidden
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: status.color }}
              />
              {status.label}
            </span>
            {dur && (
              <>
                <span className="text-[var(--r-rule)]" aria-hidden>
                  •
                </span>
                <span className="r-mono text-[var(--r-ink-2)]">{dur}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={async () => {
              setExporting(true);
              try {
                await apiDownload(
                  `/api/v1/uploads/${upload.upload_id}/shortlist.xlsx`,
                  "shortlist.xlsx",
                );
              } finally {
                setExporting(false);
              }
            }}
            disabled={exporting || !canExport}
            className="rounded-sm border border-[var(--r-rule)] bg-transparent px-3.5 py-1.5 text-xs font-medium text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-40"
          >
            {exporting ? "Exportando…" : "Exportar XLSX"}
          </button>
          <button
            type="button"
            onClick={onRetry}
            disabled={retryPending || upload.status === "pending"}
            className="rounded-sm bg-[var(--r-ink)] px-3.5 py-1.5 text-xs font-medium text-[var(--r-bg)] transition-colors hover:bg-[var(--r-accent)] disabled:opacity-40"
            title="Reprocessa o upload (reaplica consolidação e shortlist)"
          >
            {retryPending ? "Reenviando…" : "Reprocessar"}
          </button>
        </div>
      </div>
    </header>
  );
}
