// frontend/lib/api/client.ts
import { readApiBase, readTenantId } from "../tenant";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": readTenantId(),
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (init.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }
  const resp = await fetch(`${readApiBase()}${path}`, { ...init, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function apiDownload(
  path: string,
  fallbackName: string,
): Promise<void> {
  const resp = await fetch(`${readApiBase()}${path}`, {
    headers: { "X-Tenant-ID": readTenantId() },
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(detail, resp.status);
  }
  const blob = await resp.blob();
  const disposition = resp.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
