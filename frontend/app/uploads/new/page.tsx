"use client";

import { useRouter } from "next/navigation";
import { useCreateUploadMutation } from "../../../lib/api/uploads";
import { UploadDropzone } from "../../../components/upload/UploadDropzone";

export default function UploadNewPage() {
  const router = useRouter();
  const { mutate, isPending, error } = useCreateUploadMutation();

  function onFile(file: File) {
    mutate(file, {
      onSuccess: (data) => router.push(`/uploads/${data.upload_id}`),
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Novo upload</h1>
      <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-sm">
        <p className="font-medium">Antes de subir:</p>
        <ul className="ml-5 mt-2 list-disc space-y-1 text-zinc-700">
          <li>
            Arquivo <code>.csv</code> (UTF-8/Latin-1) ou <code>.xlsx</code>
          </li>
          <li>
            Coluna obrigatória com a descrição do item: <code>descricao</code>,{" "}
            <code>objeto</code>, <code>material</code>, <code>produto</code> ou{" "}
            <code>item</code>
          </li>
          <li>
            <a
              href="/upload_template.csv"
              download
              className="text-blue-600 underline"
            >
              Baixar template CSV
            </a>{" "}
            ·{" "}
            <a
              href="/UPLOAD_GUIDE.md"
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 underline"
            >
              Guia completo
            </a>
          </li>
        </ul>
      </div>
      <UploadDropzone onFile={onFile} disabled={isPending} />
      {isPending && <p className="text-sm text-zinc-500">Enviando…</p>}
      {error && <p className="text-sm text-red-600">{error.message}</p>}
    </div>
  );
}
