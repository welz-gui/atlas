"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Building2, 
  FileCheck2, 
  FolderKanban, 
  LayoutDashboard, 
  ShieldAlert, 
  FileText, 
  Compass,
  Sparkles,
  ClipboardList
} from "lucide-react";

const navItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Empreendimentos", href: "/projects", icon: Building2 },
  { name: "Copiloto de Aprovação", href: "/approvals", icon: FileCheck2 },
  { name: "Projetos e Documentos", href: "/documents", icon: FileText },
  { name: "Planejamento e EAP", href: "/plan", icon: FolderKanban },
  { name: "Diário de Obra", href: "/daily-log", icon: ClipboardList },
  { name: "Inteligência & IA", href: "/ai", icon: Sparkles },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 h-screen fixed left-0 top-0 z-40 flex flex-col glass-panel border-r border-slate-800">
      {/* Brand Header */}
      <div className="p-6 border-b border-slate-800 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <Compass className="w-6 h-6 text-white animate-pulse" />
        </div>
        <div>
          <h1 className="font-extrabold text-xl text-white tracking-wider">ATLAS</h1>
          <p className="text-[10px] uppercase tracking-widest text-cyan-400 font-semibold">Plataforma de Obras</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
          Módulos Principais
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
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
              <Icon className={`w-4 h-4 ${isActive ? "text-cyan-400" : "text-slate-400"}`} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Status / Org info */}
      <div className="p-4 border-t border-slate-800">
        <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-xs font-semibold text-slate-300">Lajeado - RS</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}
