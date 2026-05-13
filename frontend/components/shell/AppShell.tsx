import { SidebarNav } from "./SidebarNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="border-r border-zinc-200 bg-zinc-50">
        <div className="px-4 py-6">
          <h1 className="text-lg font-semibold">Agente 10</h1>
          <p className="text-xs text-zinc-500">Supplier Intelligence</p>
        </div>
        <SidebarNav />
      </aside>
      <main className="overflow-y-auto p-8">{children}</main>
    </div>
  );
}
