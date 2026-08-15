import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    // O mesmo alias do `tsconfig.json`. Sem ele, qualquer teste que importe
    // por `@/lib/...` — como o código de produção faz — falha na resolução.
    alias: { "@": path.resolve(__dirname) },
  },
});
