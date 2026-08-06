"use client";

import { usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/lib/auth";

/**
 * Decide entre o layout autenticado e a tela de acesso.
 *
 * Enquanto a sessão está sendo verificada não se renderiza nem uma coisa nem
 * outra: mostrar a aplicação antes de saber quem é o usuário produz um piscar
 * de dados de outro contexto.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const pathname = usePathname();
  const isLoginRoute = pathname === "/login";

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
      </div>
    );
  }

  if (!user || isLoginRoute) {
    return <div className="min-h-screen w-full">{children}</div>;
  }

  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Navbar />
        <main className="flex-1 ml-64 p-8 overflow-y-auto">{children}</main>
      </div>
    </>
  );
}
