"use client";

import type { UploadStatus } from "../../lib/types";

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[180px_1fr] items-baseline gap-4 border-b r-rule py-3.5 last:border-b-0">
      <p className="r-eyebrow">{label}</p>
      <p className={`text-sm text-[var(--r-ink)] ${mono ? "r-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function formatBRL(n: number | null): string {
  if (n === null) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function ReportConfigPanel({ upload }: { upload: UploadStatus }) {
  const cfg = upload.shortlist_config;
  return (
    <div className="r-card p-7">
      <p className="r-eyebrow mb-4">Configuração aplicada na geração</p>
      <Row
        label="Tamanho da shortlist"
        value={`Top ${cfg.size} por CNAE`}
        mono
      />
      <Row label="UF" value={cfg.uf ?? "todas"} />
      <Row label="Município" value={cfg.municipio ?? "todos"} />
      <Row label="Apenas matriz" value={cfg.only_matriz ? "Sim" : "Não"} />
      <Row label="Capital mínimo" value={formatBRL(cfg.min_capital)} mono />
    </div>
  );
}
