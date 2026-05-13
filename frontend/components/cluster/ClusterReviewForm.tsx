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
  const [cnae, setCnae] = useState<string | null>(cluster.cnae);
  const [notas, setNotas] = useState(cluster.notas_revisor ?? "");
  const [revisado, setRevisado] = useState(cluster.revisado_humano);
  const [feedback, setFeedback] = useState<{
    kind: "ok" | "err";
    msg: string;
  } | null>(null);

  const patch = usePatchClusterMutation(cluster.id);

  function save() {
    const body: ClusterPatchBody = {};
    if (cnae !== cluster.cnae && cnae !== null) body.cnae = cnae;
    if (notas !== (cluster.notas_revisor ?? "")) body.notas_revisor = notas;
    if (revisado !== cluster.revisado_humano) body.revisado_humano = revisado;
    if (Object.keys(body).length === 0) {
      setFeedback({ kind: "ok", msg: "Nada para salvar." });
      return;
    }
    patch.mutate(body, {
      onSuccess: () => setFeedback({ kind: "ok", msg: "Salvo." }),
      onError: (e: Error) => setFeedback({ kind: "err", msg: e.message }),
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-700">Cluster</p>
        <p className="text-lg font-semibold">{cluster.nome_cluster}</p>
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

      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-zinc-700">CNAE atual:</span>
        <span className="font-mono text-sm">{cluster.cnae ?? "—"}</span>
        <ConfidenceBadge
          metodo={cluster.cnae_metodo}
          confianca={cluster.cnae_confianca}
        />
      </div>

      <ClusterCnaeEditor value={cnae} onChange={setCnae} />

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

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={patch.isPending}>
          {patch.isPending ? "Salvando…" : "Salvar"}
        </Button>
        {feedback && (
          <span
            className={`text-sm ${
              feedback.kind === "ok" ? "text-emerald-700" : "text-red-600"
            }`}
          >
            {feedback.msg}
          </span>
        )}
      </div>
    </div>
  );
}
