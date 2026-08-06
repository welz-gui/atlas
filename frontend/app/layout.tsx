import "./globals.css";
import AppShell from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";

export const metadata = {
  title: "Atlas — Plataforma de Empreendimentos",
  description:
    "Aprovação, planejamento, execução e gestão de empreendimentos, com trilha de auditoria.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-[#090d16] text-slate-100 flex antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
