// frontend/lib/api/clusters.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./client";
import {
  ClusterDetail,
  ClusterSummary,
  Filial,
  LinhasPage,
  ShortlistEntry,
} from "../types";

export function useClustersQuery(
  uploadId: string,
  filters: { metodo?: string; revisado?: boolean } = {},
  options: { enabled?: boolean } = {},
) {
  const params = new URLSearchParams();
  if (filters.metodo) params.set("metodo", filters.metodo);
  if (filters.revisado !== undefined)
    params.set("revisado", String(filters.revisado));
  const query = params.toString();
  return useQuery({
    queryKey: ["clusters", uploadId, filters],
    queryFn: async () =>
      z
        .array(ClusterSummary)
        .parse(
          await apiFetch(
            `/api/v1/uploads/${uploadId}/clusters${query ? `?${query}` : ""}`,
          ),
        ),
    enabled: !!uploadId && (options.enabled ?? true),
  });
}

export function useClusterDetailQuery(clusterId: string) {
  return useQuery({
    queryKey: ["clusters", clusterId, "detail"],
    queryFn: async () =>
      ClusterDetail.parse(await apiFetch(`/api/v1/clusters/${clusterId}`)),
    enabled: !!clusterId,
  });
}

export function useShortlistQuery(
  clusterId: string,
  shortlistGerada: boolean | undefined,
  filters: { uf?: string; municipio?: string } = {},
) {
  const params = new URLSearchParams();
  if (filters.uf) params.set("uf", filters.uf);
  if (filters.municipio) params.set("municipio", filters.municipio);
  const query = params.toString();
  return useQuery({
    queryKey: ["clusters", clusterId, "shortlist", filters],
    queryFn: async () =>
      z
        .array(ShortlistEntry)
        .parse(
          await apiFetch(
            `/api/v1/clusters/${clusterId}/shortlist${
              query ? `?${query}` : ""
            }`,
          ),
        ),
    enabled: !!clusterId,
    refetchInterval: shortlistGerada === false ? 2000 : false,
  });
}

export function useFiliaisQuery(clusterId: string, cnpjBasico: string | null) {
  return useQuery({
    queryKey: ["clusters", clusterId, "filiais", cnpjBasico],
    queryFn: async () =>
      z
        .array(Filial)
        .parse(
          await apiFetch(
            `/api/v1/clusters/${clusterId}/empresa/${cnpjBasico}/filiais`,
          ),
        ),
    enabled: !!clusterId && !!cnpjBasico,
  });
}

export interface ClusterPatchBody {
  cnae?: string;
  cnaes_secundarios?: string[];
  notas_revisor?: string;
  revisado_humano?: boolean;
}

export function useClusterLinhasQuery(
  clusterId: string,
  page: number,
  pageSize: number = 50,
) {
  return useQuery({
    queryKey: ["clusters", clusterId, "linhas", page, pageSize],
    queryFn: async () =>
      LinhasPage.parse(
        await apiFetch(
          `/api/v1/clusters/${clusterId}/linhas?offset=${
            page * pageSize
          }&limit=${pageSize}`,
        ),
      ),
    enabled: !!clusterId,
  });
}

export function useMoveLinhasMutation(sourceClusterId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { linhaIds: string[]; targetClusterId: string }) =>
      await apiFetch<{
        moved: number;
        source_cluster_id: string;
        target_cluster_id: string;
      }>(`/api/v1/clusters/${sourceClusterId}/linhas/move`, {
        method: "POST",
        body: JSON.stringify({
          linha_ids: args.linhaIds,
          target_cluster_id: args.targetClusterId,
        }),
      }),
    onSuccess: (_data, args) => {
      // Both source and target lose their cached pages — invalidate both
      qc.invalidateQueries({
        queryKey: ["clusters", sourceClusterId, "linhas"],
      });
      qc.invalidateQueries({
        queryKey: ["clusters", args.targetClusterId, "linhas"],
      });
      // num_linhas changed on both clusters → invalidate detail + upload list
      qc.invalidateQueries({
        queryKey: ["clusters", sourceClusterId, "detail"],
      });
      qc.invalidateQueries({
        queryKey: ["clusters", args.targetClusterId, "detail"],
      });
      qc.invalidateQueries({ queryKey: ["clusters"] });
    },
  });
}

export function usePatchClusterMutation(clusterId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClusterPatchBody) =>
      ClusterDetail.parse(
        await apiFetch(`/api/v1/clusters/${clusterId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["clusters", clusterId, "detail"], data);
      qc.invalidateQueries({ queryKey: ["clusters", clusterId, "shortlist"] });
      qc.invalidateQueries({ queryKey: ["clusters", data.upload_id] });
    },
  });
}
