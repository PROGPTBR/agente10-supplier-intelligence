// frontend/components/upload/UploadProgressBar.tsx
import { Progress } from "../ui/progress";

export function UploadProgressBar({
  status,
  pct,
  erro,
}: {
  status: string;
  pct: number;
  erro?: string | null;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Status: {status}</span>
        <span className="text-zinc-500">{pct.toFixed(0)}%</span>
      </div>
      <Progress value={pct} aria-label="Progresso do upload" />
      {erro && <p className="text-sm text-red-600">Erro: {erro}</p>}
    </div>
  );
}
