// frontend/components/dashboard/StatCard.tsx
export function StatCard({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
}) {
  return (
    <div className="r-card p-6">
      <p className="r-eyebrow">{label}</p>
      <p className="r-display mt-3 text-3xl text-[var(--r-ink)]">{value}</p>
      {sublabel && (
        <p className="mt-1.5 text-xs text-[var(--r-ink-2)]">{sublabel}</p>
      )}
    </div>
  );
}
