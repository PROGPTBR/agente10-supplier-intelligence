// frontend/lib/tenant.ts
export function readTenantId(): string {
  const tenant = process.env.NEXT_PUBLIC_TENANT_ID;
  if (!tenant) {
    throw new Error("NEXT_PUBLIC_TENANT_ID env var is required");
  }
  return tenant;
}

export function readApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}
