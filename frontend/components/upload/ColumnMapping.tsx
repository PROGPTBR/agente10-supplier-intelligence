"use client";

import { useState } from "react";
import type { UploadPreview } from "../../lib/api/uploads";

const INTERNAL_FIELDS: { key: string; label: string; required: boolean }[] = [
  { key: "descricao_original", label: "Descrição do item *", required: true },
  { key: "agrupamento", label: "Agrupamento / categoria", required: false },
  { key: "id_linha_origem", label: "Código / ID do material", required: false },
  { key: "fornecedor_atual", label: "Fornecedor atual", required: false },
  { key: "cnpj_fornecedor", label: "CNPJ do fornecedor", required: false },
  { key: "valor_total", label: "Valor total", required: false },
  { key: "quantidade", label: "Quantidade", required: false },
  { key: "uf_solicitante", label: "UF", required: false },
  { key: "municipio_solicitante", label: "Município", required: false },
  { key: "centro_custo", label: "Centro de custo", required: false },
  { key: "data_compra", label: "Data da compra", required: false },
];

export interface ColumnMappingProps {
  preview: UploadPreview;
  onConfirm: (mapping: Record<string, string>) => void;
  onCancel: () => void;
  disabled?: boolean;
}

export function ColumnMapping({
  preview,
  onConfirm,
  onCancel,
  disabled,
}: ColumnMappingProps) {
  // For each internal field, what raw column maps to it. Initialize from auto_mapping.
  const initial: Record<string, string> = {};
  Object.entries(preview.auto_mapping).forEach(([rawCol, internal]) => {
    if (!initial[internal]) initial[internal] = rawCol;
  });
  const [field2col, setField2col] = useState<Record<string, string>>(initial);

  const canSubmit = !!field2col["descricao_original"];

  function handleSubmit() {
    // Build mapping: raw column → internal field
    const mapping: Record<string, string> = {};
    Object.entries(field2col).forEach(([internal, rawCol]) => {
      if (rawCol) mapping[rawCol] = internal;
    });
    onConfirm(mapping);
  }

  return (
    <div className="space-y-4 rounded-lg border border-amber-300 bg-amber-50 p-4">
      <div>
        <h3 className="font-semibold text-amber-900">
          Mapeamento de colunas necessário
        </h3>
        <p className="mt-1 text-sm text-amber-800">
          Não conseguimos identificar automaticamente qual coluna do seu arquivo
          tem a descrição do item. Mapeie pelo menos a coluna obrigatória.
        </p>
      </div>

      <div className="rounded border border-amber-200 bg-white p-2 text-xs">
        <p className="mb-1 font-medium text-zinc-600">
          Primeiras linhas do arquivo:
        </p>
        <div className="overflow-x-auto">
          <table className="text-zinc-700">
            <thead>
              <tr>
                {preview.columns.map((c, i) => (
                  <th
                    key={i}
                    className="border-b border-zinc-200 px-2 py-1 text-left font-medium"
                  >
                    {c || `(coluna ${i + 1})`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.sample_rows.slice(0, 3).map((row, i) => (
                <tr key={i}>
                  {preview.columns.map((_, j) => (
                    <td key={j} className="border-b border-zinc-100 px-2 py-1">
                      {row[j] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {INTERNAL_FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col text-sm">
            <span className="mb-1 text-zinc-700">
              {f.label}
              {f.required && (
                <span className="ml-1 text-red-600" aria-label="obrigatório">
                  *
                </span>
              )}
            </span>
            <select
              value={field2col[f.key] ?? ""}
              onChange={(e) =>
                setField2col({ ...field2col, [f.key]: e.target.value })
              }
              className="rounded border border-zinc-300 bg-white px-2 py-1"
              disabled={disabled}
            >
              <option value="">— não mapear —</option>
              {preview.columns.map((c, i) => (
                <option key={i} value={c}>
                  {c || `(coluna ${i + 1})`}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit || disabled}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Confirmar mapeamento e processar
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className="rounded border border-zinc-300 bg-white px-4 py-2 text-sm text-zinc-700"
        >
          Cancelar
        </button>
      </div>

      {!canSubmit && (
        <p className="text-xs text-amber-800">
          Selecione qual coluna tem a descrição do item para continuar.
        </p>
      )}
    </div>
  );
}
