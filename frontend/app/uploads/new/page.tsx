"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  useCreateUploadMutation,
  usePreviewUploadMutation,
  type UploadPreview,
} from "../../../lib/api/uploads";
import { UploadDropzone } from "../../../components/upload/UploadDropzone";
import { ColumnMapping } from "../../../components/upload/ColumnMapping";

export default function UploadNewPage() {
  const router = useRouter();
  const preview = usePreviewUploadMutation();
  const create = useCreateUploadMutation();
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<UploadPreview | null>(null);

  function submitWithMapping(file: File, mapping?: Record<string, string>) {
    create.mutate(
      { file, columnMapping: mapping },
      { onSuccess: (data) => router.push(`/uploads/${data.upload_id}`) },
    );
  }

  function onFile(file: File) {
    setPendingFile(file);
    setPreviewData(null);
    preview.mutate(file, {
      onSuccess: (p) => {
        if (!p.needs_mapping) {
          submitWithMapping(file);
        } else {
          setPreviewData(p);
        }
      },
    });
  }

  const isWorking = preview.isPending || create.isPending;
  const error = preview.error?.message ?? create.error?.message ?? null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Novo upload</h1>

      {!previewData && (
        <>
          <div className="rounded border border-zinc-200 bg-zinc-50 p-4 text-sm">
            <p className="font-medium">Antes de subir:</p>
            <ul className="ml-5 mt-2 list-disc space-y-1 text-zinc-700">
              <li>
                Arquivo <code>.csv</code> (UTF-8/Latin-1) ou <code>.xlsx</code>
              </li>
              <li>
                Pelo menos uma coluna com descrição do item (
                <code>descricao</code>, <code>objeto</code>,{" "}
                <code>material</code>, …). Se a sua não bater, mapeamos no passo
                seguinte.
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
          <UploadDropzone onFile={onFile} disabled={isWorking} />
        </>
      )}

      {previewData && pendingFile && (
        <ColumnMapping
          preview={previewData}
          disabled={create.isPending}
          onConfirm={(mapping) => submitWithMapping(pendingFile, mapping)}
          onCancel={() => {
            setPendingFile(null);
            setPreviewData(null);
          }}
        />
      )}

      {preview.isPending && (
        <p className="text-sm text-zinc-500">Lendo cabeçalho do arquivo…</p>
      )}
      {create.isPending && (
        <p className="text-sm text-zinc-500">Enviando para processamento…</p>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
