// frontend/lib/types.ts
import { z } from "zod";

export const UploadSummary = z.object({
  upload_id: z.string().uuid(),
  nome_arquivo: z.string(),
  status: z.string(),
  linhas_total: z.number(),
  linhas_classificadas: z.number(),
  data_upload: z.string(),
  progresso_pct: z.number(),
});
export type UploadSummary = z.infer<typeof UploadSummary>;

export const UploadStatus = z.object({
  upload_id: z.string().uuid(),
  status: z.string(),
  linhas_total: z.number(),
  linhas_classificadas: z.number(),
  erro: z.string().nullable(),
  progresso_pct: z.number(),
});
export type UploadStatus = z.infer<typeof UploadStatus>;

export const ClusterSummary = z.object({
  id: z.string().uuid(),
  nome_cluster: z.string(),
  cnae: z.string().nullable(),
  cnae_descricao: z.string().nullable(),
  cnae_confianca: z.number().nullable(),
  cnae_metodo: z.string().nullable(),
  num_linhas: z.number(),
  revisado_humano: z.boolean(),
  shortlist_size: z.number(),
});
export type ClusterSummary = z.infer<typeof ClusterSummary>;

export const ClusterDetail = z.object({
  id: z.string().uuid(),
  upload_id: z.string().uuid(),
  nome_cluster: z.string(),
  cnae: z.string().nullable(),
  cnae_descricao: z.string().nullable(),
  cnae_confianca: z.number().nullable(),
  cnae_metodo: z.string().nullable(),
  num_linhas: z.number(),
  revisado_humano: z.boolean(),
  notas_revisor: z.string().nullable(),
  shortlist_gerada: z.boolean(),
  sample_linhas: z.array(z.string()),
});
export type ClusterDetail = z.infer<typeof ClusterDetail>;

export const ShortlistEntry = z.object({
  cnpj: z.string(),
  razao_social: z.string(),
  nome_fantasia: z.string().nullable(),
  capital_social: z.number().nullable(),
  uf: z.string().nullable(),
  municipio: z.string().nullable(),
  data_abertura: z.string().nullable(),
  rank_estagio3: z.number(),
});
export type ShortlistEntry = z.infer<typeof ShortlistEntry>;

export const DashboardStats = z.object({
  uploads_total: z.number(),
  uploads_done: z.number(),
  clusters_total: z.number(),
  clusters_revised: z.number(),
  clusters_by_metodo: z.record(z.string(), z.number()),
  shortlists_total: z.number(),
  recent_uploads: z.array(UploadSummary),
});
export type DashboardStats = z.infer<typeof DashboardStats>;
