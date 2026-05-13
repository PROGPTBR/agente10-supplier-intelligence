// frontend/components/cluster/ConfidenceBadge.tsx
import { Badge } from "../ui/badge";

const STYLES: Record<string, { className: string; label: string }> = {
  retrieval: { className: "bg-emerald-100 text-emerald-800", label: "Auto" },
  curator: { className: "bg-sky-100 text-sky-800", label: "Curator" },
  manual_pending: { className: "bg-amber-100 text-amber-800", label: "Manual" },
  retrieval_fallback: {
    className: "bg-zinc-100 text-zinc-700",
    label: "Fallback",
  },
  revisado_humano: {
    className: "bg-purple-100 text-purple-800",
    label: "Revisado",
  },
};

export function ConfidenceBadge({
  metodo,
  confianca,
}: {
  metodo: string | null;
  confianca: number | null;
}) {
  if (!metodo) return <Badge variant="secondary">—</Badge>;
  const style = STYLES[metodo] ?? {
    className: "bg-zinc-100 text-zinc-700",
    label: metodo,
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${style.className}`}
      aria-label={`Método ${style.label}, confiança ${
        confianca?.toFixed(2) ?? "n/d"
      }`}
    >
      <span>{style.label}</span>
      {confianca !== null && (
        <span className="opacity-70">{(confianca * 100).toFixed(0)}%</span>
      )}
    </span>
  );
}
