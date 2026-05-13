// frontend/tests/api/client.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFetch } from "../../lib/api/client";

describe("apiFetch", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_TENANT_ID = "00000000-0000-0000-0000-000000000001";
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
    global.fetch = vi.fn();
  });

  it("injects X-Tenant-ID header", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    } as Response);

    await apiFetch("/x");

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const init = call[1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-Tenant-ID"]).toBe(
      "00000000-0000-0000-0000-000000000001",
    );
    expect(call[0]).toBe("http://api.test/x");
  });

  it("throws on non-ok response with detail", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "bad request" }),
    } as Response);

    await expect(apiFetch("/x")).rejects.toThrow(/bad request/);
  });
});
