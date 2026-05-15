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
      <label className="flex flex-col gap-1">
        <span className="r-eyebrow">UF</span>
        <select
          value={value.uf}
          onChange={(e) => onChange({ ...value, uf: e.target.value })}
          className="r-mono rounded-lg border bg-[var(--r-surface)] px-3 py-2 text-xs text-[var(--r-ink)] r-rule focus:border-[var(--r-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--r-primary-soft)]"
        >
          <option value="">— todas —</option>
          {UFS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="r-eyebrow">Município</span>
        <input
          type="text"
          value={value.municipio}
          onChange={(e) => onChange({ ...value, municipio: e.target.value })}
          placeholder="ex: SAO PAULO"
          className="rounded-lg border bg-[var(--r-surface)] px-3 py-2 text-xs text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--r-primary-soft)]"
        />
      </label>
      {(value.uf || value.municipio) && (
        <button
          type="button"
          onClick={() => onChange({ uf: "", municipio: "" })}
          className="r-btn-ghost text-[10px] uppercase tracking-wider"
        >
          Limpar
        </button>
      )}
    </div>
  );
}
