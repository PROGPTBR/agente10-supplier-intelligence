// frontend/lib/api/uploads.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./client";
import { UploadStatus, UploadSummary } from "../types";

export function useUploadsQuery() {
  return useQuery({
    queryKey: ["uploads"],
    queryFn: async () =>
      z.array(UploadSummary).parse(await apiFetch("/api/v1/uploads")),
  });
}

export function useUploadStatusQuery(uploadId: string) {
  return useQuery({
    queryKey: ["uploads", uploadId],
    queryFn: async () =>
      UploadStatus.parse(await apiFetch(`/api/v1/uploads/${uploadId}`)),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
    enabled: !!uploadId,
  });
}

export function useCreateUploadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("nome_arquivo", file.name);
      return await apiFetch<{ upload_id: string; status: string }>(
        "/api/v1/uploads",
        { method: "POST", body: fd },
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["uploads"] }),
  });
}
