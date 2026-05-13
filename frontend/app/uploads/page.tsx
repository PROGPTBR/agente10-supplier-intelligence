"use client";

import Link from "next/link";
import { useUploadsQuery } from "../../lib/api/uploads";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

const STATUS_VARIANT = {
  done: "default",
  processing: "secondary",
  pending: "secondary",
  failed: "destructive",
} as const;

export default function UploadsListPage() {
  const { data, isLoading, error } = useUploadsQuery();
  if (isLoading) return <p className="text-sm text-zinc-500">Carregando…</p>;
  if (error || !data) {
    return <p className="text-sm text-red-600">Erro ao carregar uploads.</p>;
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Uploads</h1>
        <Button render={<Link href="/uploads/new" />}>Novo upload</Button>
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-zinc-500">
          Nenhum upload ainda — comece{" "}
          <Link href="/uploads/new" className="underline">
            enviando um CSV
          </Link>
          .
        </p>
      ) : (
        <table className="w-full border-separate border-spacing-0 text-sm">
          <thead className="text-left text-xs text-zinc-500">
            <tr>
              <th className="border-b border-zinc-200 pb-2">Arquivo</th>
              <th className="border-b border-zinc-200 pb-2">Status</th>
              <th className="border-b border-zinc-200 pb-2">Linhas</th>
              <th className="border-b border-zinc-200 pb-2">Progresso</th>
              <th className="border-b border-zinc-200 pb-2">Data</th>
            </tr>
          </thead>
          <tbody>
            {data.map((u) => (
              <tr key={u.upload_id} className="hover:bg-zinc-50">
                <td className="border-b border-zinc-100 py-3">
                  <Link
                    href={`/uploads/${u.upload_id}`}
                    className="font-medium text-zinc-900 hover:underline"
                  >
                    {u.nome_arquivo}
                  </Link>
                </td>
                <td className="border-b border-zinc-100 py-3">
                  <Badge
                    variant={
                      (
                        STATUS_VARIANT as Record<
                          string,
                          "default" | "secondary" | "destructive"
                        >
                      )[u.status] ?? "secondary"
                    }
                  >
                    {u.status}
                  </Badge>
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-700">
                  {u.linhas_classificadas}/{u.linhas_total}
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-700">
                  {u.progresso_pct.toFixed(0)}%
                </td>
                <td className="border-b border-zinc-100 py-3 text-zinc-500">
                  {new Date(u.data_upload).toLocaleString("pt-BR")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
