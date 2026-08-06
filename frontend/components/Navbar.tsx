"use client";

import { useEffect, useState } from "react";
import { Building, LogOut, ShieldCheck } from "lucide-react";
import { Organization, fetchOrganization } from "@/lib/api";
import { ROLE_LABELS, useAuth } from "@/lib/auth";

export default function Navbar() {
  const { user, signOut } = useAuth();
  const [organization, setOrganization] = useState<Organization | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchOrganization()
      .then(setOrganization)
      .catch(() => setOrganization(null));
  }, [user]);

  if (!user) return null;

  return (
    <header className="ml-64 h-16 border-b border-slate-800 glass-panel flex items-center justify-between px-8 sticky top-0 z-30">
      <div className="flex items-center gap-2 text-xs text-slate-400 min-w-0">
        <Building className="w-4 h-4 text-slate-500 shrink-0" />
        <span className="font-semibold text-slate-300 truncate">
          {organization?.name ?? "Organização"}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800">
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <div className="text-right leading-tight">
            <p className="text-[11px] font-semibold text-slate-200">{user.name}</p>
            <p className="text-[10px] text-cyan-400">{ROLE_LABELS[user.role]}</p>
          </div>
        </div>

        <button
          onClick={signOut}
          className="p-2 rounded-lg text-slate-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
          title="Sair"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
