import { redirect } from "next/navigation";

export default async function UploadDetailRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/relatorios/${id}`);
}
