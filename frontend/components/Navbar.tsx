"use client";

import { Bell, Search, User, ChevronDown, CheckCircle2 } from "lucide-react";

export default function Navbar() {
  return (
    <header className="h-16 ml-64 border-b border-slate-800 glass-panel sticky top-0 z-30 flex items-center justify-between px-6">
      {/* Search Input */}
      <div className="relative w-96">
        <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Buscar empreendimento, regra normativa ou documento..."
          className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900/80 border border-slate-700/60 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors placeholder:text-slate-500"
        />
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Baseline Status Badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-medium">
          <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />
          <span>Linha de Base Ativa</span>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors">
          <Bell className="w-4 h-4" />
          <span className="w-2 h-2 rounded-full bg-cyan-400 absolute top-1.5 right-1.5" />
        </button>

        {/* User Profile */}
        <div className="flex items-center gap-3 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center font-bold text-xs text-white shadow-inner">
            EA
          </div>
          <div className="text-left hidden sm:block">
            <p className="text-xs font-semibold text-slate-200">Eng. Delta</p>
            <p className="text-[10px] text-slate-400">Construtora Delta</p>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        </div>
      </div>
    </header>
  );
}
