// frontend/lib/api/clusters.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./client";
import { ClusterDetail, ClusterSummary, ShortlistEntry } from "../types";

export function useClustersQuery(
  uploadId: string,
  filters: { metodo?: string; revisado?: boolean } = {},
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
    enabled: !!uploadId,
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
) {
  return useQuery({
    queryKey: ["clusters", clusterId, "shortlist"],
    queryFn: async () =>
      z
        .array(ShortlistEntry)
        .parse(await apiFetch(`/api/v1/clusters/${clusterId}/shortlist`)),
    enabled: !!clusterId,
    refetchInterval: shortlistGerada === false ? 2000 : false,
  });
}

export interface ClusterPatchBody {
  cnae?: string;
  notas_revisor?: string;
  revisado_humano?: boolean;
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
