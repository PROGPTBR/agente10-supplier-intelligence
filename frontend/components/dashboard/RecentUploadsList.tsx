// frontend/components/dashboard/RecentUploadsList.tsx
import Link from "next/link";
import { Badge } from "../ui/badge";
import type { UploadSummary } from "../../lib/types";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> =
  {
    done: "default",
    processing: "secondary",
    pending: "secondary",
    failed: "destructive",
  };

export function RecentUploadsList({ uploads }: { uploads: UploadSummary[] }) {
  if (uploads.length === 0) {
    return <p className="text-sm text-zinc-500">Nenhum upload ainda.</p>;
  }
  return (
    <ul className="divide-y divide-zinc-200">
      {uploads.map((u) => (
        <li
          key={u.upload_id}
          className="flex items-center justify-between py-3"
        >
          <Link
            href={`/uploads/${u.upload_id}`}
            className="text-sm font-medium text-zinc-900 hover:underline"
          >
            {u.nome_arquivo}
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500">
              {u.linhas_classificadas}/{u.linhas_total} linhas
            </span>
            <Badge variant={STATUS_VARIANT[u.status] ?? "secondary"}>
              {u.status}
            </Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}
