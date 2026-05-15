"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard", num: "01" },
  { href: "/uploads", label: "Relatórios", num: "02" },
];

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="px-3 pt-2" aria-label="Navegação principal">
      <ul className="flex flex-col">
        {NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`group relative flex items-baseline gap-3 px-3 py-3 transition-colors ${
                  active
                    ? "text-[var(--r-ink)]"
                    : "text-[var(--r-ink-2)] hover:text-[var(--r-ink)]"
                }`}
              >
                <span
                  aria-hidden
                  className="r-mono w-5 shrink-0 text-[10px] tracking-wider"
                  style={{
                    color: active ? "var(--r-accent)" : "var(--r-ink-3)",
                  }}
                >
                  {item.num}
                </span>
                <span className="r-serif text-lg italic">{item.label}</span>
                {active && (
                  <span
                    aria-hidden
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2"
                    style={{ backgroundColor: "var(--r-accent)" }}
                  />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
