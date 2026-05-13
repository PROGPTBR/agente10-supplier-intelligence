// frontend/lib/api/dashboard.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { DashboardStats } from "../types";

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: async () =>
      DashboardStats.parse(await apiFetch("/api/v1/dashboard/stats")),
    refetchOnWindowFocus: true,
  });
}
