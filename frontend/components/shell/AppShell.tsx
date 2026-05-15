import Link from "next/link";
import { SidebarNav } from "./SidebarNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-[232px_1fr]">
      <aside
        className="flex flex-col border-r"
        style={{
          borderColor: "var(--r-rule)",
          backgroundColor: "var(--r-bg)",
        }}
      >
        <Link
          href="/dashboard"
          className="block px-6 pt-8 pb-6 group focus:outline-none"
          aria-label="Agente 10 — ir para o dashboard"
        >
          <p className="r-eyebrow mb-1">Agente 10</p>
          <h1 className="r-serif text-3xl italic leading-none text-[var(--r-ink)] transition-colors group-hover:text-[var(--r-accent)]">
            Supplier
            <br />
            Intelligence
          </h1>
          <div
            aria-hidden
            className="mt-3 h-px w-12"
            style={{ backgroundColor: "var(--r-accent)" }}
          />
        </Link>
        <SidebarNav />
        <div className="mt-auto px-6 pb-6">
          <p
            className="r-mono text-[10px] tracking-wider text-[var(--r-ink-3)]"
            aria-hidden
          >
            v1 · piloto
          </p>
        </div>
      </aside>
      <main className="overflow-y-auto p-8 lg:p-12">{children}</main>
    </div>
  );
}
