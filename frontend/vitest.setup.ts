import "@testing-library/jest-dom/vitest";
// `lib/api.ts` guarda o token em `localStorage`, que o jsdom não implementa.
const store: Record<string, string> = {};

Object.defineProperty(window, "localStorage", {
  value: {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      for (const key of Object.keys(store)) delete store[key];
    },
  },
});
