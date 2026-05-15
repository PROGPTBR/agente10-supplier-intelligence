import Link from "next/link";
import { IAgenticsLogo } from "../brand/IAgenticsLogo";
import { SidebarNav } from "./SidebarNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-[256px_1fr]">
      <aside
        className="relative flex flex-col text-white"
        style={{ background: "var(--r-gradient)" }}
      >
        {/* Soft inner glow at the top */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-48"
          style={{
            background:
              "radial-gradient(60% 80% at 50% 0%, rgba(255,255,255,0.18) 0%, transparent 70%)",
          }}
        />

        <Link
          href="/dashboard"
          className="relative z-10 px-6 pt-7 pb-8 transition-opacity hover:opacity-90"
          aria-label="IAgentics — ir para o dashboard"
        >
          <IAgenticsLogo size={28} tone="light" />
          <p className="mt-1.5 ml-[40px] text-[10px] uppercase tracking-[0.18em] text-white/60">
            Supplier Intelligence
          </p>
        </Link>

        <SidebarNav />

        <div className="relative z-10 mt-auto px-6 pb-6">
          <div
            aria-hidden
            className="mb-4 h-px"
            style={{
              background:
                "linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)",
            }}
          />
          <p className="text-[10px] tracking-wider text-white/50">
            v1 · piloto ELETROBRÁS
          </p>
        </div>
      </aside>
      <main className="overflow-y-auto p-8 lg:p-12">{children}</main>
    </div>
  );
}
