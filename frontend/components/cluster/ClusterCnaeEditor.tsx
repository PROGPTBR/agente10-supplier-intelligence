"use client";

import { useMemo, useState } from "react";
import cnaeData from "../../lib/cnae-taxonomy.json";

interface Cnae {
  codigo: string;
  denominacao: string;
}

const ALL_CNAES = cnaeData as Cnae[];

export function ClusterCnaeEditor({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (next: string) => void;
}) {
  const [query, setQuery] = useState("");
  const matches = useMemo(() => {
    if (!query.trim()) return ALL_CNAES.slice(0, 20);
    const q = query.toLowerCase();
    return ALL_CNAES.filter(
      (c) => c.codigo.includes(q) || c.denominacao.toLowerCase().includes(q),
    ).slice(0, 20);
  }, [query]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-zinc-700">CNAE</label>
      <input
        type="search"
        placeholder="Pesquisar por código ou descrição…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
        aria-label="Pesquisar CNAE"
      />
      <ul
        className="max-h-64 overflow-y-auto rounded-md border border-zinc-200"
        role="listbox"
      >
        {matches.map((c) => (
          <li
            key={c.codigo}
            onClick={() => onChange(c.codigo)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onChange(c.codigo);
            }}
            role="option"
            aria-selected={value === c.codigo}
            tabIndex={0}
            className={`cursor-pointer px-3 py-2 text-sm hover:bg-zinc-50 ${
              value === c.codigo ? "bg-emerald-50" : ""
            }`}
          >
            <span className="font-mono text-zinc-600">{c.codigo}</span>{" "}
            <span className="text-zinc-900">{c.denominacao}</span>
          </li>
        ))}
        {matches.length === 0 && (
          <li className="px-3 py-2 text-sm text-zinc-500">
            Nenhum CNAE encontrado.
          </li>
        )}
      </ul>
    </div>
  );
}
