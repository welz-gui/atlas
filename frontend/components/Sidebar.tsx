"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  ClipboardList,
  Compass,
  FileCheck2,
  FileText,
  FolderKanban,
  Gavel,
  LayoutDashboard,
  ScrollText,
  Search,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV_SECTIONS: {
  title: string;
  items: { name: string; href: string; icon: typeof LayoutDashboard; permission?: string }[];
}[] = [
  {
    title: "Empreendimento",
    items: [
      { name: "Painel", href: "/", icon: LayoutDashboard },
      { name: "Empreendimentos", href: "/projects", icon: Building2 },
      { name: "Copiloto de Aprovação", href: "/approvals", icon: FileCheck2 },
      { name: "Tramitação", href: "/protocol", icon: Gavel },
      { name: "Projetos e Documentos", href: "/documents", icon: FileText },
    ],
  },
  {
    title: "Regulatório",
    items: [
      { name: "Catálogo de Regras", href: "/catalog", icon: ScrollText },
      { name: "Assistente Normativo", href: "/ai", icon: Search },
    ],
  },
  {
    title: "Obra",
    items: [
      { name: "Planejamento e EAP", href: "/plan", icon: FolderKanban },
      { name: "Diário de Obra", href: "/daily-log", icon: ClipboardList },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="w-64 h-screen fixed left-0 top-0 z-40 flex flex-col glass-panel border-r border-slate-800">
      <div className="p-6 border-b border-slate-800 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <Compass className="w-6 h-6 text-white" />
        </div>
        <div className="min-w-0">
          <h1 className="font-extrabold text-xl text-white tracking-wider">ATLAS</h1>
          <p className="text-[10px] uppercase tracking-widest text-cyan-400 font-semibold">
            Plataforma de obras
          </p>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-4 overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title} className="space-y-1">
            <div className="px-3 py-1 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              {section.title}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? "bg-gradient-to-r from-blue-600/30 to-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? "text-cyan-400" : "text-slate-400"
                    }`}
                  />
                  <span className="truncate">{item.name}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <span className="text-xs font-semibold text-slate-300 truncate">
              {user ? user.email : "—"}
            </span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono shrink-0">v2.0</span>
        </div>
      </div>
    </aside>
  );
}
