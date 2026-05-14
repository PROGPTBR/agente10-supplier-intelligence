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
      <label className="flex flex-col text-xs text-zinc-600">
        UF
        <select
          value={value.uf}
          onChange={(e) => onChange({ ...value, uf: e.target.value })}
          className="mt-1 rounded border border-zinc-300 bg-white px-2 py-1 text-sm"
        >
          <option value="">— todas —</option>
          {UFS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-xs text-zinc-600">
        Município
        <input
          type="text"
          value={value.municipio}
          onChange={(e) => onChange({ ...value, municipio: e.target.value })}
          placeholder="ex: SAO PAULO"
          className="mt-1 rounded border border-zinc-300 bg-white px-2 py-1 text-sm"
        />
      </label>
      {(value.uf || value.municipio) && (
        <button
          type="button"
          onClick={() => onChange({ uf: "", municipio: "" })}
          className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
        >
          Limpar
        </button>
      )}
    </div>
  );
}
