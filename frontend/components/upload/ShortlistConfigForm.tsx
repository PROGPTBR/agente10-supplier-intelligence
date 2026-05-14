"use client";

import type { ShortlistConfig } from "../../lib/types";

const SIZES = [10, 20, 50, 100] as const;

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

export const DEFAULT_SHORTLIST_CONFIG: ShortlistConfig = {
  size: 10,
  uf: null,
  municipio: null,
  only_matriz: false,
  min_capital: null,
};

export function ShortlistConfigForm({
  value,
  onChange,
  disabled,
}: {
  value: ShortlistConfig;
  onChange: (v: ShortlistConfig) => void;
  disabled?: boolean;
}) {
  return (
    <div className="rounded border border-zinc-200 bg-white p-4">
      <div className="mb-3">
        <p className="text-sm font-medium text-zinc-900">
          Configuração da shortlist
        </p>
        <p className="text-xs text-zinc-500">
          Define quantos fornecedores por CNAE e quais filtros aplicar. Aplicado
          na geração — o curator reranqueia já dentro deste recorte.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col text-xs text-zinc-600">
          Tamanho da shortlist (por CNAE)
          <select
            value={value.size}
            onChange={(e) =>
              onChange({
                ...value,
                size: Number(e.target.value) as ShortlistConfig["size"],
              })
            }
            disabled={disabled}
            className="mt-1 rounded border border-zinc-300 bg-white px-2 py-1 text-sm"
          >
            {SIZES.map((s) => (
              <option key={s} value={s}>
                Top {s}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col text-xs text-zinc-600">
          UF (estado)
          <select
            value={value.uf ?? ""}
            onChange={(e) => onChange({ ...value, uf: e.target.value || null })}
            disabled={disabled}
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
            value={value.municipio ?? ""}
            onChange={(e) =>
              onChange({ ...value, municipio: e.target.value || null })
            }
            placeholder="ex: SAO PAULO"
            disabled={disabled}
            className="mt-1 rounded border border-zinc-300 bg-white px-2 py-1 text-sm"
          />
        </label>

        <label className="flex flex-col text-xs text-zinc-600">
          Capital social mínimo (BRL)
          <input
            type="number"
            min={0}
            step={100000}
            value={value.min_capital ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                min_capital: e.target.value ? Number(e.target.value) : null,
              })
            }
            placeholder="opcional"
            disabled={disabled}
            className="mt-1 rounded border border-zinc-300 bg-white px-2 py-1 text-sm"
          />
        </label>

        <label className="col-span-full flex items-center gap-2 text-sm text-zinc-700">
          <input
            type="checkbox"
            checked={value.only_matriz}
            onChange={(e) =>
              onChange({ ...value, only_matriz: e.target.checked })
            }
            disabled={disabled}
          />
          Apenas matriz (CNPJ terminado em 0001)
        </label>
      </div>
    </div>
  );
}
