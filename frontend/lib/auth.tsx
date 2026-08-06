"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ApiError,
  CurrentUser,
  UserRole,
  fetchCurrentUser,
  getToken,
  login as apiLogin,
  logout as apiLogout,
  setUnauthorizedHandler,
} from "@/lib/api";

/**
 * Matriz de permissões do cliente.
 *
 * Espelha `app/core/security.py`. É conveniência de interface — esconder um
 * botão não é controle de acesso; quem decide é sempre o servidor.
 */
const PERMISSIONS: Record<string, UserRole[]> = {
  "org:manage": ["owner", "admin"],
  "project:write": ["owner", "admin", "engineer"],
  "project:baseline": ["owner", "admin", "engineer"],
  "document:write": ["owner", "admin", "engineer", "inspector"],
  "catalog:validate": ["owner", "admin", "validator"],
  "protocol:write": ["owner", "admin", "engineer"],
  "field:write": ["owner", "admin", "engineer", "inspector"],
};

export const ROLE_LABELS: Record<UserRole, string> = {
  owner: "Responsável",
  admin: "Administrador",
  validator: "Validador técnico",
  engineer: "Engenharia",
  inspector: "Campo",
  client: "Cliente",
};

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  error: ApiError | Error | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  can: (permission: string) => boolean;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Rotas que não exigem sessão. */
const PUBLIC_ROUTES = ["/login"];

/**
 * Onde cada papel começa.
 *
 * O cliente entra no portal, não no painel operacional (§8.22). Não é
 * controle de acesso — o servidor é quem recusa —, é não colocar diante do
 * contratante uma tela cheia de informação em conferência técnica.
 */
function homeFor(role: UserRole): string {
  return role === "client" ? "/portal" : "/";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const loadUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      setUser(await fetchCurrentUser());
      setError(null);
    } catch (err) {
      setUser(null);
      // 401 já limpou o token no cliente HTTP; outros erros viram mensagem.
      if (!(err instanceof ApiError && err.isUnauthorized)) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // Token expirado em qualquer requisição derruba a sessão em toda a aplicação.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      router.replace("/login");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  // Guarda de rota: sem sessão, só as rotas públicas respondem.
  useEffect(() => {
    if (isLoading) return;
    const isPublic = PUBLIC_ROUTES.includes(pathname);
    if (!user && !isPublic) router.replace("/login");
    if (user && isPublic) router.replace(homeFor(user.role));
    // O painel operacional não é a casa do cliente; o portal é.
    if (user && user.role === "client" && pathname === "/") router.replace("/portal");
  }, [user, isLoading, pathname, router]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const signed = await apiLogin(email, password);
      setUser(signed);
      setError(null);
      router.replace(homeFor(signed.role));
    },
    [router]
  );

  const signOut = useCallback(() => {
    apiLogout();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const can = useCallback(
    (permission: string) => {
      if (!user) return false;
      const roles = PERMISSIONS[permission];
      // Permissão desconhecida aqui significa "somente leitura", liberada a
      // qualquer sessão autenticada — o servidor faz a checagem real.
      return roles ? roles.includes(user.role) : true;
    },
    [user]
  );

  const value = useMemo(
    () => ({ user, isLoading, error, signIn, signOut, can, refresh: loadUser }),
    [user, isLoading, error, signIn, signOut, can, loadUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth precisa estar dentro de <AuthProvider>.");
  }
  return context;
}
