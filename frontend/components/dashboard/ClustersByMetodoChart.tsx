// frontend/components/dashboard/ClustersByMetodoChart.tsx
const COLORS: Record<string, string> = {
  retrieval: "bg-emerald-500",
  curator: "bg-sky-500",
  manual_pending: "bg-amber-500",
  retrieval_fallback: "bg-zinc-500",
  revisado_humano: "bg-purple-500",
};

const LABELS: Record<string, string> = {
  retrieval: "Auto",
  curator: "Curator LLM",
  manual_pending: "Manual",
  retrieval_fallback: "Fallback",
  revisado_humano: "Revisado",
};

export function ClustersByMetodoChart({
  data,
}: {
  data: Record<string, number>;
}) {
  const total = Object.values(data).reduce((s, n) => s + n, 0) || 1;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-zinc-700">Clusters por método</p>
      <div className="flex h-3 overflow-hidden rounded-full bg-zinc-100">
        {Object.entries(data).map(([k, n]) => (
          <div
            key={k}
            className={COLORS[k] ?? "bg-zinc-400"}
            style={{ width: `${(n / total) * 100}%` }}
            aria-label={`${LABELS[k] ?? k}: ${n}`}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-3 text-xs">
        {Object.entries(data).map(([k, n]) => (
          <li key={k} className="flex items-center gap-1.5">
            <span
              className={`inline-block size-2 rounded-sm ${
                COLORS[k] ?? "bg-zinc-400"
              }`}
            />
            <span className="text-zinc-700">
              {LABELS[k] ?? k}: {n}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
