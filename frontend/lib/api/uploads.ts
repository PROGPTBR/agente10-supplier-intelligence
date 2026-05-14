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

export type UploadPreview = {
  columns: string[];
  auto_mapping: Record<string, string>;
  sample_rows: string[][];
  needs_mapping: boolean;
};

export function usePreviewUploadMutation() {
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return await apiFetch<UploadPreview>("/api/v1/uploads/preview", {
        method: "POST",
        body: fd,
      });
    },
  });
}

export function useCreateUploadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: {
      file: File;
      columnMapping?: Record<string, string>;
    }) => {
      const fd = new FormData();
      fd.append("file", args.file);
      fd.append("nome_arquivo", args.file.name);
      if (args.columnMapping && Object.keys(args.columnMapping).length > 0) {
        fd.append("column_mapping", JSON.stringify(args.columnMapping));
      }
      return await apiFetch<{ upload_id: string; status: string }>(
        "/api/v1/uploads",
        { method: "POST", body: fd },
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["uploads"] }),
  });
}

export function useRetryUploadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (uploadId: string) =>
      await apiFetch<{ upload_id: string; status: string }>(
        `/api/v1/uploads/${uploadId}/retry`,
        { method: "POST" },
      ),
    onSuccess: (_data, uploadId) => {
      qc.invalidateQueries({ queryKey: ["uploads"] });
      qc.invalidateQueries({ queryKey: ["uploads", uploadId] });
    },
  });
}

export function useDeleteUploadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (uploadId: string) =>
      await apiFetch<void>(`/api/v1/uploads/${uploadId}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["uploads"] }),
  });
}
