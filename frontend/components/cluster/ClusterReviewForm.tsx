"use client";

import { useState } from "react";
import type { ClusterDetail } from "../../lib/types";
import {
  usePatchClusterMutation,
  type ClusterPatchBody,
} from "../../lib/api/clusters";
import { ClusterCnaeEditor } from "./ClusterCnaeEditor";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Button } from "../ui/button";

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
      setFeedback({
        kind: "err",
        msg: "Já é o CNAE principal.",
      });
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

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-700">Cluster</p>
        <p className="text-lg font-semibold">
          {cluster.nome_cluster_refinado ?? cluster.nome_cluster}
        </p>
        {cluster.nome_cluster_refinado &&
          cluster.nome_cluster_refinado !== cluster.nome_cluster && (
            <p className="text-xs text-zinc-500">
              Nome bruto do clusterizador:{" "}
              <span className="font-mono">{cluster.nome_cluster}</span>
            </p>
          )}
        <p className="mt-1 text-xs text-zinc-500">
          {cluster.num_linhas} linhas
        </p>
      </div>

      {cluster.sample_linhas.length > 0 && (
        <div>
          <p className="text-sm font-medium text-zinc-700">Amostra de linhas</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-zinc-700">
            {cluster.sample_linhas.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-zinc-700">CNAE atual:</span>
        <span className="font-mono text-sm">{cluster.cnae ?? "—"}</span>
        <ConfidenceBadge
          metodo={cluster.cnae_metodo}
          confianca={cluster.cnae_confianca}
        />
      </div>

      {cluster.cnaes_secundarios.length > 0 && (
        <div>
          <p className="text-sm font-medium text-zinc-700">
            CNAEs alternativos
          </p>
          <div className="mt-1 flex flex-wrap gap-2">
            {cluster.cnaes_secundarios.map((code) => (
              <span
                key={code}
                className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs"
              >
                <span className="font-mono">{code}</span>
                <button
                  type="button"
                  onClick={() => removeAlternative(code)}
                  disabled={patch.isPending}
                  className="text-zinc-500 hover:text-red-600 disabled:opacity-50"
                  title="Remover alternativo"
                  aria-label={`Remover CNAE alternativo ${code}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <ClusterCnaeEditor value={picked} onChange={setPicked} />

      <div className="flex flex-wrap gap-3">
        <Button
          onClick={replacePrimary}
          disabled={patch.isPending || !picked}
          title="Substitui o CNAE principal e regenera a shortlist"
        >
          {patch.isPending ? "Salvando…" : "Substituir CNAE atual"}
        </Button>
        <Button
          onClick={addAlternative}
          disabled={patch.isPending || !picked}
          title="Adiciona como CNAE alternativo (mantém o atual e gera shortlist para ambos)"
        >
          {patch.isPending ? "Salvando…" : "Adicionar como alternativo"}
        </Button>
        {feedback && (
          <span
            className={`self-center text-sm ${
              feedback.kind === "ok" ? "text-emerald-700" : "text-red-600"
            }`}
          >
            {feedback.msg}
          </span>
        )}
      </div>

      <div>
        <label
          htmlFor="notas"
          className="block text-sm font-medium text-zinc-700"
        >
          Notas do revisor
        </label>
        <textarea
          id="notas"
          value={notas}
          onChange={(e) => setNotas(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={revisado}
          onChange={(e) => setRevisado(e.target.checked)}
        />
        Marcar como revisado
      </label>

      <div>
        <Button onClick={saveOtherFields} disabled={patch.isPending}>
          {patch.isPending ? "Salvando…" : "Salvar notas / revisado"}
        </Button>
      </div>
    </div>
  );
}
