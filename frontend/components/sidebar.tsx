"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Table2, Bell, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

const itens = [
  { href: "/", label: "Visão geral", icone: LayoutDashboard },
  { href: "/leituras", label: "Leituras", icone: Table2 },
  { href: "/alertas", label: "Alertas", icone: Bell },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex md:w-60 md:flex-col md:fixed md:inset-y-0 md:border-r md:bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Cpu className="h-6 w-6 text-primary" />
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold">UNIVESP · PI VI</span>
          <span className="text-xs text-muted-foreground">Monitoramento</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {itens.map((item) => {
          const Icone = item.icone;
          const ativo =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                ativo
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icone className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-4 text-xs text-muted-foreground">
        <p>Projeto Integrador VI</p>
        <p>UNIVESP · 2026</p>
      </div>
    </aside>
  );
}
