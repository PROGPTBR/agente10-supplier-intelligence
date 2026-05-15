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
  revisado_humano: { label: "Revisado humano", color: "#10B981" },
  curator: { label: "Curator (LLM)", color: "#5B3FE5" },
  retrieval: { label: "Retrieval", color: "#8C84FF" },
  cache: { label: "Cache", color: "#A4C5FF" },
  golden: { label: "Golden seed", color: "#F59E0B" },
  manual_pending: { label: "Pendente manual", color: "#EF4444" },
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

  function addAlternativeCode(code: string) {
    if (code === cluster.cnae) {
      setFeedback({ kind: "err", msg: "Já é o CNAE principal." });
      return;
    }
    if (cluster.cnaes_secundarios.includes(code)) {
      setFeedback({ kind: "err", msg: "Já está nos alternativos." });
      return;
    }
    sendPatch(
      {
        cnaes_secundarios: [...cluster.cnaes_secundarios, code],
        notas_revisor: notas || undefined,
      },
      "CNAE alternativo adicionado. Shortlist regenerando…",
    );
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
    addAlternativeCode(picked);
  }

  function removeAlternative(code: string) {
    sendPatch(
      {
        cnaes_secundarios: cluster.cnaes_secundarios.filter((c) => c !== code),
      },
      "Alternativo removido. Shortlist regenerando…",
    );
  }

  function toggleAlternative(code: string) {
    if (code === cluster.cnae) return;
    if (cluster.cnaes_secundarios.includes(code)) {
      removeAlternative(code);
    } else {
      addAlternativeCode(code);
    }
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
    <div className="space-y-7">
      {/* CNAE atual */}
      <section className="r-card p-6">
        <div className="flex items-baseline justify-between gap-4">
          <p className="r-eyebrow">CNAE atual</p>
          {metodoInfo && (
            <span
              className="r-pill"
              style={{
                backgroundColor: `${metodoInfo.color}1f`,
                color: metodoInfo.color,
              }}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: metodoInfo.color }}
              />
              {metodoInfo.label}
              {conf !== null && (
                <span className="r-mono ml-1 opacity-70">
                  {(conf * 100).toFixed(0)}%
                </span>
              )}
            </span>
          )}
        </div>
        <div className="mt-4 flex items-baseline gap-4">
          <span className="r-display text-4xl text-[var(--r-ink)]">
            {cluster.cnae ?? "—"}
          </span>
          {cluster.cnae && (
            <span className="text-sm text-[var(--r-ink-2)]">
              {denomFor(cluster.cnae)}
            </span>
          )}
        </div>
      </section>

      {/* Secundários */}
      {cluster.cnaes_secundarios.length > 0 && (
        <section>
          <p className="r-eyebrow mb-3">CNAEs alternativos</p>
          <ul className="flex flex-wrap gap-2">
            {cluster.cnaes_secundarios.map((code) => (
              <li
                key={code}
                className="r-pill"
                style={{
                  backgroundColor: "var(--r-primary-soft)",
                  color: "var(--r-primary)",
                  padding: "5px 12px",
                }}
              >
                <span className="r-mono font-semibold">{code}</span>
                <span className="hidden text-[var(--r-ink-2)] sm:inline">
                  {denomFor(code).slice(0, 36)}
                  {denomFor(code).length > 36 ? "…" : ""}
                </span>
                <button
                  type="button"
                  onClick={() => removeAlternative(code)}
                  disabled={patch.isPending}
                  className="ml-1 opacity-50 transition-opacity hover:opacity-100 disabled:opacity-20"
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
      <section className="space-y-4">
        <p className="r-eyebrow">Pesquisar novo CNAE</p>
        <ClusterCnaeEditor
          value={picked}
          onChange={setPicked}
          currentPrimary={cluster.cnae}
          currentSecondaries={cluster.cnaes_secundarios}
          onDoubleClickCode={toggleAlternative}
        />

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={replacePrimary}
            disabled={patch.isPending || !picked}
            className="r-btn-primary"
            title="Substitui o CNAE principal e regenera a shortlist"
          >
            {patch.isPending ? "Salvando…" : "Substituir principal"}
          </button>
          <button
            type="button"
            onClick={addAlternative}
            disabled={patch.isPending || !picked}
            className="r-btn-ghost"
            title="Adiciona como CNAE alternativo (mantém o atual)"
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
      <section className="r-card space-y-4 p-6">
        <p className="r-eyebrow">Notas do revisor</p>
        <textarea
          id="notas"
          value={notas}
          onChange={(e) => setNotas(e.target.value)}
          rows={3}
          placeholder="Anotações opcionais sobre a classificação…"
          className="w-full rounded-xl border bg-[var(--r-bg)] px-3 py-2 text-sm text-[var(--r-ink)] r-rule placeholder:text-[var(--r-ink-3)] focus:border-[var(--r-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--r-primary-soft)]"
        />
        <label className="flex items-center gap-2 text-sm text-[var(--r-ink-2)]">
          <input
            type="checkbox"
            checked={revisado}
            onChange={(e) => setRevisado(e.target.checked)}
            className="h-4 w-4 rounded accent-[var(--r-primary)]"
          />
          Marcar como revisado
        </label>
        <button
          type="button"
          onClick={saveOtherFields}
          disabled={patch.isPending}
          className="r-btn-ghost"
        >
          {patch.isPending ? "Salvando…" : "Salvar notas / revisado"}
        </button>
      </section>
    </div>
  );
}
