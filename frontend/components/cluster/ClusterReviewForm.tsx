"use client";

import { useState } from "react";
import cnaeData from "../../lib/cnae-taxonomy.json";
import type { ClusterDetail } from "../../lib/types";
import {
  usePatchClusterMutation,
  type ClusterPatchBody,
} from "../../lib/api/clusters";
import { ClusterCnaeEditor } from "./ClusterCnaeEditor";

interface CnaeRef {
  codigo: string;
  denominacao: string;
}

const CNAE_BY_CODE = new Map<string, string>(
  (cnaeData as CnaeRef[]).map((c) => [c.codigo, c.denominacao]),
);

function denomFor(code: string | null): string {
  if (!code) return "";
  return CNAE_BY_CODE.get(code) ?? "";
}

const METODO_LABEL: Record<string, { label: string; color: string }> = {
  revisado_humano: { label: "Revisado humano", color: "var(--r-success)" },
  curator: { label: "Curator (LLM)", color: "var(--r-ink)" },
  retrieval: { label: "Retrieval", color: "var(--r-ink-2)" },
  cache: { label: "Cache", color: "var(--r-ink-3)" },
  golden: { label: "Golden seed", color: "var(--r-warning)" },
  manual_pending: { label: "Pendente manual", color: "var(--r-accent)" },
};

export function ClusterReviewForm({ cluster }: { cluster: ClusterDetail }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [notas, setNotas] = useState(cluster.notas_revisor ?? "");
  const [revisado, setRevisado] = useState(cluster.revisado_humano);
  const [feedback, setFeedback] = useState<{
    kind: "ok" | "err";
    msg: string;
  } | null>(null);

  const patch = usePatchClusterMutation(cluster.id);

  function sendPatch(body: ClusterPatchBody, okMsg: string) {
    patch.mutate(body, {
      onSuccess: () => {
        setFeedback({ kind: "ok", msg: okMsg });
        setPicked(null);
      },
      onError: (e: Error) => setFeedback({ kind: "err", msg: e.message }),
    });
  }

  function replacePrimary() {
    if (!picked) return;
    sendPatch(
      { cnae: picked, notas_revisor: notas || undefined },
      "CNAE principal substituído. Shortlist regenerando…",
    );
  }

  function addAlternative() {
    if (!picked) return;
    if (picked === cluster.cnae) {
      setFeedback({ kind: "err", msg: "Já é o CNAE principal." });
      return;
    }
    if (cluster.cnaes_secundarios.includes(picked)) {
      setFeedback({ kind: "err", msg: "Já está nos alternativos." });
      return;
    }
    sendPatch(
      {
        cnaes_secundarios: [...cluster.cnaes_secundarios, picked],
        notas_revisor: notas || undefined,
      },
      "CNAE alternativo adicionado. Shortlist regenerando…",
    );
  }

  function removeAlternative(code: string) {
    sendPatch(
      {
        cnaes_secundarios: cluster.cnaes_secundarios.filter((c) => c !== code),
      },
      "Alternativo removido. Shortlist regenerando…",
    );
  }

  function saveOtherFields() {
    const body: ClusterPatchBody = {};
    if (notas !== (cluster.notas_revisor ?? "")) body.notas_revisor = notas;
    if (revisado !== cluster.revisado_humano) body.revisado_humano = revisado;
    if (Object.keys(body).length === 0) {
      setFeedback({ kind: "ok", msg: "Nada para salvar." });
      return;
    }
    sendPatch(body, "Salvo.");
  }

  const metodoInfo = cluster.cnae_metodo
    ? METODO_LABEL[cluster.cnae_metodo] ?? {
        label: cluster.cnae_metodo,
        color: "var(--r-ink-2)",
      }
    : null;
  const conf = cluster.cnae_confianca;

  return (
    <div className="space-y-10">
      {/* CNAE atual — display */}
      <section className="r-rise space-y-3">
        <div className="flex items-baseline justify-between gap-4">
          <p className="r-eyebrow">CNAE atual</p>
          {metodoInfo && (
            <span
              className="r-mono text-[10px] uppercase tracking-wider"
              style={{ color: metodoInfo.color }}
            >
              ● {metodoInfo.label}
              {conf !== null && (
                <span className="ml-2 text-[var(--r-ink-2)]">
                  {(conf * 100).toFixed(0)}%
                </span>
              )}
            </span>
          )}
        </div>
        <div className="flex items-baseline gap-4 border-b r-rule pb-4">
          <span className="r-serif text-5xl italic text-[var(--r-ink)]">
            {cluster.cnae ?? "—"}
          </span>
          {cluster.cnae && (
            <span className="r-serif text-base italic text-[var(--r-ink-2)]">
              {denomFor(cluster.cnae)}
            </span>
          )}
        </div>
      </section>

      {/* Secundários */}
      {cluster.cnaes_secundarios.length > 0 && (
        <section
          className="r-rise space-y-3"
          style={{ animationDelay: "80ms" }}
        >
          <p className="r-eyebrow">CNAEs alternativos</p>
          <ul className="flex flex-wrap gap-2">
            {cluster.cnaes_secundarios.map((code) => (
              <li
                key={code}
                className="group inline-flex items-center gap-2 border r-rule bg-[var(--r-surface)] px-3 py-1.5 text-xs"
              >
                <span className="r-mono text-[var(--r-ink)]">{code}</span>
                <span className="hidden text-[var(--r-ink-2)] sm:inline">
                  {denomFor(code).slice(0, 40)}
                  {denomFor(code).length > 40 ? "…" : ""}
                </span>
                <button
                  type="button"
                  onClick={() => removeAlternative(code)}
                  disabled={patch.isPending}
                  className="ml-1 text-[var(--r-ink-3)] transition-colors hover:text-[var(--r-danger)] disabled:opacity-40"
                  title="Remover alternativo"
                  aria-label={`Remover CNAE alternativo ${code}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Picker + ações */}
      <section
        className="r-rise space-y-4 border-t r-rule pt-8"
        style={{ animationDelay: "160ms" }}
      >
        <p className="r-eyebrow">Pesquisar novo CNAE</p>
        <ClusterCnaeEditor value={picked} onChange={setPicked} />

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={replacePrimary}
            disabled={patch.isPending || !picked}
            className="rounded-sm bg-[var(--r-ink)] px-4 py-2 text-xs font-medium text-[var(--r-bg)] transition-colors hover:bg-[var(--r-accent)] disabled:opacity-40"
            title="Substitui o CNAE principal e regenera a shortlist"
          >
            {patch.isPending ? "Salvando…" : "Substituir CNAE principal"}
          </button>
          <button
            type="button"
            onClick={addAlternative}
            disabled={patch.isPending || !picked}
            className="rounded-sm border border-[var(--r-rule)] bg-transparent px-4 py-2 text-xs font-medium text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-40"
            title="Adiciona como CNAE alternativo (mantém o atual e gera shortlist para ambos)"
          >
            Adicionar como alternativo
          </button>
          {feedback && (
            <span
              className="text-xs"
              style={{
                color:
                  feedback.kind === "ok"
                    ? "var(--r-success)"
                    : "var(--r-danger)",
              }}
            >
              {feedback.msg}
            </span>
          )}
        </div>
      </section>

      {/* Notas + revisado */}
      <section
        className="r-rise space-y-4 border-t r-rule pt-8"
        style={{ animationDelay: "240ms" }}
      >
        <p className="r-eyebrow">Notas do revisor</p>
        <textarea
          id="notas"
          value={notas}
          onChange={(e) => setNotas(e.target.value)}
          rows={3}
          placeholder="Anotações opcionais sobre a classificação…"
          className="w-full border bg-[var(--r-surface)] px-3 py-2 text-sm text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-accent)] focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm text-[var(--r-ink-2)]">
          <input
            type="checkbox"
            checked={revisado}
            onChange={(e) => setRevisado(e.target.checked)}
            className="h-4 w-4 accent-[var(--r-accent)]"
          />
          Marcar como revisado
        </label>
        <button
          type="button"
          onClick={saveOtherFields}
          disabled={patch.isPending}
          className="rounded-sm border border-[var(--r-rule)] bg-transparent px-4 py-2 text-xs font-medium text-[var(--r-ink)] transition-colors hover:bg-[var(--r-accent-soft)] disabled:opacity-40"
        >
          {patch.isPending ? "Salvando…" : "Salvar notas / revisado"}
        </button>
      </section>
    </div>
  );
}
