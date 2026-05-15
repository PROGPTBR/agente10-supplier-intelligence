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
  currentPrimary,
  currentSecondaries,
  onDoubleClickCode,
}: {
  value: string | null;
  onChange: (next: string) => void;
  currentPrimary?: string | null;
  currentSecondaries?: string[];
  onDoubleClickCode?: (code: string) => void;
}) {
  const [query, setQuery] = useState("");
  const matches = useMemo(() => {
    if (!query.trim()) return ALL_CNAES.slice(0, 20);
    const q = query.toLowerCase();
    return ALL_CNAES.filter(
      (c) => c.codigo.includes(q) || c.denominacao.toLowerCase().includes(q),
    ).slice(0, 20);
  }, [query]);

  const secSet = new Set(currentSecondaries ?? []);

  return (
    <div className="space-y-2">
      <input
        type="search"
        placeholder="Pesquisar por código ou descrição…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-xl border bg-[var(--r-surface)] px-3.5 py-2.5 text-sm text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--r-primary-soft)]"
        aria-label="Pesquisar CNAE"
      />
      {onDoubleClickCode && (
        <p className="text-[11px] text-[var(--r-ink-3)]">
          Duplo clique adiciona/remove como alternativo
        </p>
      )}
      <ul
        className="max-h-64 overflow-y-auto rounded-xl border r-rule bg-[var(--r-surface)]"
        role="listbox"
      >
        {matches.map((c) => {
          const isPrimary = c.codigo === currentPrimary;
          const isSecondary = secSet.has(c.codigo);
          const isPicked = value === c.codigo;
          return (
            <li
              key={c.codigo}
              onClick={() => onChange(c.codigo)}
              onDoubleClick={() => {
                if (isPrimary) return;
                onDoubleClickCode?.(c.codigo);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") onChange(c.codigo);
              }}
              role="option"
              aria-selected={isPicked}
              tabIndex={0}
              className="cursor-pointer select-none px-3 py-2.5 text-sm transition-colors hover:bg-[var(--r-surface-2)]"
              style={
                isPicked
                  ? { backgroundColor: "var(--r-primary-soft)" }
                  : undefined
              }
              title={
                isPrimary
                  ? "É o CNAE principal"
                  : isSecondary
                    ? "Já alternativo — duplo clique remove"
                    : onDoubleClickCode
                      ? "Duplo clique adiciona como alternativo"
                      : undefined
              }
            >
              <div className="flex items-baseline gap-3">
                <span className="r-mono shrink-0 text-xs font-semibold text-[var(--r-ink-2)]">
                  {c.codigo}
                </span>
                <span className="truncate text-[var(--r-ink)]">
                  {c.denominacao}
                </span>
                {isPrimary && (
                  <span
                    className="ml-auto shrink-0 r-pill"
                    style={{
                      backgroundColor: "var(--r-ink)",
                      color: "#fff",
                    }}
                  >
                    principal
                  </span>
                )}
                {!isPrimary && isSecondary && (
                  <span
                    className="ml-auto shrink-0 r-pill"
                    style={{
                      backgroundColor: "var(--r-primary-soft)",
                      color: "var(--r-primary)",
                    }}
                  >
                    alternativo
                  </span>
                )}
              </div>
            </li>
          );
        })}
        {matches.length === 0 && (
          <li className="px-3 py-2 text-sm text-[var(--r-ink-2)]">
            Nenhum CNAE encontrado.
          </li>
        )}
      </ul>
    </div>
  );
}
