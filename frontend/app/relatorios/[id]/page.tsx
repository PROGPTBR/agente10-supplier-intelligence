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
    <div className="report-page -m-8 min-h-screen p-8 lg:p-12">
      <div className="mx-auto max-w-6xl space-y-0">
        {upload.isLoading && (
          <p className="r-serif text-xl italic text-[var(--r-ink-2)]">
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
                className="r-rise mt-8 rounded-sm border-l-4 bg-[var(--r-surface)] p-5"
                style={{ borderColor: "var(--r-danger)" }}
              >
                <p className="r-eyebrow mb-2 text-[var(--r-danger)]">
                  Processamento falhou
                </p>
                <pre className="r-mono max-h-24 overflow-auto whitespace-pre-wrap text-xs text-[var(--r-ink)]">
                  {upload.data.erro.slice(0, 600)}
                </pre>
              </div>
            )}

            {upload.data.status === "pending" ? (
              <p
                className="r-serif r-rise mt-16 text-center text-2xl italic text-[var(--r-ink-2)]"
                style={{ animationDelay: "120ms" }}
              >
                Processamento iniciado. Aguarde alguns instantes…
              </p>
            ) : (
              <div className="mt-10 space-y-0">
                <ReportHero upload={upload.data} />

                {classificationDone && clusters.data && (
                  <>
                    <ReportMetodoBreakdown clusters={clusters.data} />
                    <ReportTopCategorias clusters={clusters.data} />
                  </>
                )}

                {!classificationDone && upload.data.status === "processing" && (
                  <section
                    className="r-rise border-b r-rule py-10"
                    style={{ animationDelay: "240ms" }}
                  >
                    <p className="r-eyebrow mb-2">Pipeline em curso</p>
                    <p className="r-serif text-xl italic text-[var(--r-ink-2)]">
                      Gráficos disponíveis ao terminar a classificação.
                    </p>
                  </section>
                )}

                <section
                  className="r-rise pt-10"
                  style={{ animationDelay: "480ms" }}
                >
                  <Tabs defaultValue="clusters" className="w-full">
                    <TabsList>
                      <TabsTrigger value="clusters">Clusters</TabsTrigger>
                      <TabsTrigger value="config">Configuração</TabsTrigger>
                    </TabsList>

                    <TabsContent value="clusters">
                      {!classificationDone ? (
                        <p className="text-sm text-[var(--r-ink-2)]">
                          Clusters aparecem aqui quando a classificação
                          terminar.
                        </p>
                      ) : (
                        <div className="space-y-4">
                          <ClusterFilters
                            value={filters}
                            onChange={setFilters}
                          />
                          {clusters.isLoading && (
                            <p className="text-sm text-[var(--r-ink-2)]">
                              Carregando clusters…
                            </p>
                          )}
                          {clusters.data && (
                            <ClusterTable
                              clusters={clusters.data}
                              searchTerm={filters.search}
                            />
                          )}
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="config">
                      <ReportConfigPanel upload={upload.data} />
                    </TabsContent>
                  </Tabs>
                </section>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
