"use client";

import { use, useState } from "react";
import { useClustersQuery } from "../../../lib/api/clusters";
import {
  useRetryUploadMutation,
  useUploadStatusQuery,
} from "../../../lib/api/uploads";
import {
  ClusterFilters,
  type ClusterFilterState,
} from "../../../components/cluster/ClusterFilters";
import { ClusterTable } from "../../../components/cluster/ClusterTable";
import { ReportHeader } from "../../../components/report/ReportHeader";
import { ReportHero } from "../../../components/report/ReportHero";
import { ReportMetodoBreakdown } from "../../../components/report/ReportMetodoBreakdown";
import { ReportTopCategorias } from "../../../components/report/ReportTopCategorias";
import { ReportConfigPanel } from "../../../components/report/ReportConfigPanel";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../../components/ui/tabs";

export default function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const upload = useUploadStatusQuery(id);
  const retry = useRetryUploadMutation();
  const [filters, setFilters] = useState<ClusterFilterState>({ search: "" });

  const classificationDone =
    upload.data !== undefined &&
    upload.data.linhas_total > 0 &&
    upload.data.linhas_classificadas >= upload.data.linhas_total;

  const clusters = useClustersQuery(
    id,
    { metodo: filters.metodo, revisado: filters.revisado },
    { enabled: classificationDone },
  );

  return (
    <div className="mx-auto max-w-6xl">
      {upload.isLoading && (
        <p className="r-display text-xl text-[var(--r-ink-2)]">
          Carregando relatório…
        </p>
      )}
      {upload.error && (
        <p className="text-sm text-[var(--r-danger)]">
          Relatório não encontrado.
        </p>
      )}
      {upload.data && (
        <>
          <ReportHeader
            upload={upload.data}
            filename={upload.data.nome_arquivo}
            onRetry={() => retry.mutate(id)}
            retryPending={retry.isPending}
          />

          {upload.data.status === "failed" && upload.data.erro && (
            <div
              className="r-rise mt-8 rounded-2xl p-5"
              style={{
                background: "rgba(239,68,68,0.06)",
                border: "1px solid rgba(239,68,68,0.2)",
              }}
            >
              <p className="r-eyebrow mb-2" style={{ color: "#B91C1C" }}>
                Processamento falhou
              </p>
              <pre className="r-mono max-h-24 overflow-auto whitespace-pre-wrap text-xs text-[var(--r-ink)]">
                {upload.data.erro.slice(0, 600)}
              </pre>
            </div>
          )}

          {upload.data.status === "pending" ? (
            <p
              className="r-display r-rise mt-16 text-center text-2xl text-[var(--r-ink-2)]"
              style={{ animationDelay: "120ms" }}
            >
              Processamento iniciado. Aguarde alguns instantes…
            </p>
          ) : (
            <>
              <ReportHero upload={upload.data} />

              {classificationDone && clusters.data && (
                <>
                  <ReportMetodoBreakdown clusters={clusters.data} />
                  <ReportTopCategorias clusters={clusters.data} />
                </>
              )}

              {!classificationDone && upload.data.status === "processing" && (
                <section
                  className="r-card r-rise mt-6 p-7"
                  style={{ animationDelay: "200ms" }}
                >
                  <p className="r-eyebrow mb-2">Pipeline em curso</p>
                  <p className="r-display text-xl text-[var(--r-ink-2)]">
                    Gráficos disponíveis ao terminar a classificação.
                  </p>
                </section>
              )}

              <section
                className="r-rise mt-10"
                style={{ animationDelay: "360ms" }}
              >
                <Tabs defaultValue="clusters" className="w-full">
                  <TabsList>
                    <TabsTrigger value="clusters">Clusters</TabsTrigger>
                    <TabsTrigger value="config">Configuração</TabsTrigger>
                  </TabsList>

                  <TabsContent value="clusters">
                    {!classificationDone ? (
                      <p className="text-sm text-[var(--r-ink-2)]">
                        Clusters aparecem aqui quando a classificação terminar.
                      </p>
                    ) : (
                      <div className="space-y-4">
                        <ClusterFilters value={filters} onChange={setFilters} />
                        {clusters.isLoading && (
                          <p className="text-sm text-[var(--r-ink-2)]">
                            Carregando clusters…
                          </p>
                        )}
                        {clusters.data && (
                          <div className="r-card p-2">
                            <ClusterTable
                              clusters={clusters.data}
                              searchTerm={filters.search}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="config">
                    <ReportConfigPanel upload={upload.data} />
                  </TabsContent>
                </Tabs>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
