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
      <UploadDropzone onFile={onFile} disabled={isPending} />
      {isPending && <p className="text-sm text-zinc-500">Enviando…</p>}
      {error && <p className="text-sm text-red-600">{error.message}</p>}
    </div>
  );
}
