"use client";

import Link from "next/link";
import { useState } from "react";
import { apiDownload } from "../../lib/api/client";
import type { UploadStatus } from "../../lib/types";

const STATUS_LABEL: Record<
  string,
  { label: string; bg: string; fg: string; dot: string }
> = {
  done: {
    label: "Concluído",
    bg: "rgba(16,185,129,0.12)",
    fg: "#047857",
    dot: "#10B981",
  },
  processing: {
    label: "Processando",
    bg: "rgba(91,63,229,0.12)",
    fg: "var(--r-primary)",
    dot: "var(--r-primary)",
  },
  pending: {
    label: "Aguardando",
    bg: "var(--r-surface-2)",
    fg: "var(--r-ink-2)",
    dot: "var(--r-ink-3)",
  },
  failed: {
    label: "Falhou",
    bg: "rgba(239,68,68,0.12)",
    fg: "#B91C1C",
    dot: "#EF4444",
  },
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

      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="space-y-3">
          <h1 className="r-display text-4xl leading-none text-[var(--r-ink)] sm:text-[44px]">
            {filename.replace(/\.(csv|xlsx)$/i, "")}
          </h1>
          <div className="flex items-center gap-3 text-sm">
            <span
              className="r-pill"
              style={{ backgroundColor: status.bg, color: status.fg }}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: status.dot }}
              />
              {status.label}
            </span>
            {dur && (
              <span className="r-mono text-xs text-[var(--r-ink-2)]">
                {dur}
              </span>
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
            className="r-btn-ghost"
          >
            {exporting ? "Exportando…" : "Exportar XLSX"}
          </button>
          <button
            type="button"
            onClick={onRetry}
            disabled={retryPending || upload.status === "pending"}
            className="r-btn-primary"
            title="Reprocessa o upload (reaplica consolidação e shortlist)"
          >
            {retryPending ? "Reenviando…" : "Reprocessar"}
          </button>
        </div>
      </div>
    </header>
  );
}
