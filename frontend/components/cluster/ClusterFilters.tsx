// frontend/components/cluster/ClusterFilters.tsx
"use client";

import { Input } from "../ui/input";

export interface ClusterFilterState {
  metodo?: string;
  revisado?: boolean;
  search: string;
}

export function ClusterFilters({
  value,
  onChange,
}: {
  value: ClusterFilterState;
  onChange: (next: ClusterFilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        type="search"
        placeholder="Buscar cluster…"
        value={value.search}
        onChange={(e) => onChange({ ...value, search: e.target.value })}
        className="w-64"
        aria-label="Buscar cluster"
      />
      <select
        value={value.metodo ?? ""}
        onChange={(e) =>
          onChange({ ...value, metodo: e.target.value || undefined })
        }
        className="rounded-md border border-zinc-300 px-3 py-2 text-sm"
        aria-label="Filtrar por método"
      >
        <option value="">Todos os métodos</option>
        <option value="retrieval">Auto (retrieval)</option>
        <option value="curator">Curator</option>
        <option value="manual_pending">Manual pending</option>
        <option value="retrieval_fallback">Fallback</option>
        <option value="revisado_humano">Revisado</option>
      </select>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value.revisado === true}
          onChange={(e) =>
            onChange({ ...value, revisado: e.target.checked || undefined })
          }
        />
        Apenas revisados
      </label>
    </div>
  );
}
