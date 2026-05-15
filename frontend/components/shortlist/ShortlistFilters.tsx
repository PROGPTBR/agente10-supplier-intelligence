"use client";

export interface ShortlistFilterState {
  uf: string;
  municipio: string;
}

const UFS = [
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
];

export function ShortlistFilters({
  value,
  onChange,
}: {
  value: ShortlistFilterState;
  onChange: (v: ShortlistFilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="r-eyebrow flex flex-col gap-1">
        UF
        <select
          value={value.uf}
          onChange={(e) => onChange({ ...value, uf: e.target.value })}
          className="r-mono mt-1 border bg-[var(--r-surface)] px-2 py-1 text-xs text-[var(--r-ink)] r-rule focus:border-[var(--r-accent)] focus:outline-none"
        >
          <option value="">— todas —</option>
          {UFS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </label>
      <label className="r-eyebrow flex flex-col gap-1">
        Município
        <input
          type="text"
          value={value.municipio}
          onChange={(e) => onChange({ ...value, municipio: e.target.value })}
          placeholder="ex: SAO PAULO"
          className="mt-1 border bg-[var(--r-surface)] px-2 py-1 text-xs text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-accent)] focus:outline-none"
        />
      </label>
      {(value.uf || value.municipio) && (
        <button
          type="button"
          onClick={() => onChange({ uf: "", municipio: "" })}
          className="rounded-sm border border-[var(--r-rule)] bg-transparent px-2 py-1 text-[10px] uppercase tracking-wider text-[var(--r-ink-2)] hover:bg-[var(--r-accent-soft)]"
        >
          Limpar
        </button>
      )}
    </div>
  );
}
