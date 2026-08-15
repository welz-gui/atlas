"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { createQueryClient } from "@/lib/queryClient";

/**
 * Provedor do cliente de consultas (§6.1 — D8).
 *
 * O cliente nasce dentro de `useState` e não no escopo do módulo: no App
 * Router o módulo é avaliado no servidor, e um cliente compartilhado ali
 * misturaria o cache de requisições de usuários diferentes. Uma instância por
 * montagem mantém o cache preso à sessão do navegador.
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
