// frontend/components/upload/UploadProgressBar.tsx
import { Progress } from "../ui/progress";

export function UploadProgressBar({
  status,
  pct,
  erro,
  clustersTotal,
  clustersClassificados,
  clustersComShortlist,
}: {
  status: string;
  pct: number;
  erro?: string | null;
  clustersTotal?: number;
  clustersClassificados?: number;
  clustersComShortlist?: number;
}) {
  const showCounters = typeof clustersTotal === "number" && clustersTotal > 0;
  const shortlistPct =
    showCounters && typeof clustersComShortlist === "number"
      ? (clustersComShortlist / clustersTotal!) * 100
      : 0;

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            Status: {status}
            {status === "processing" && pct >= 100 && (
              <span className="ml-2 text-xs font-normal text-amber-700">
                · gerando shortlists de fornecedores…
              </span>
            )}
          </span>
          <span className="text-zinc-500">{pct.toFixed(0)}%</span>
        </div>
        <Progress value={pct} aria-label="Progresso de classificação" />
        <p className="text-xs text-zinc-500">Classificação CNAE das linhas</p>
      </div>

      {showCounters && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded border border-zinc-200 bg-zinc-50 p-2">
            <p className="text-zinc-500">Clusters identificados</p>
            <p className="text-sm font-semibold">
              {clustersClassificados ?? 0} / {clustersTotal}
            </p>
          </div>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-2">
            <p className="text-zinc-500">Shortlists geradas</p>
            <p className="text-sm font-semibold">
              {clustersComShortlist ?? 0} / {clustersTotal}{" "}
              <span className="text-zinc-400">
                ({shortlistPct.toFixed(0)}%)
              </span>
            </p>
          </div>
        </div>
      )}

      {erro && <p className="text-sm text-red-600">Erro: {erro}</p>}
    </div>
  );
}
