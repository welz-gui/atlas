import type { Metadata, Viewport } from "next";

import "./globals.css";
import AppShell from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
import { QueryProvider } from "./providers";

export const metadata: Metadata = {
  title: "Atlas — Plataforma de Empreendimentos",
  description:
    "Aprovação, planejamento, execução e gestão de empreendimentos, com trilha de auditoria.",
  manifest: "/manifest.webmanifest",
  // Instalável no celular do técnico de campo (§6.2). O que funciona sem rede
  // é o registro de obra; análise e laudo continuam exigindo conexão (§3.7).
  applicationName: "Atlas",
  appleWebApp: {
    capable: true,
    title: "Atlas",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#090d16",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-[#090d16] text-slate-100 flex antialiased">
        <QueryProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
