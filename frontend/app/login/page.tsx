"use client";

import { useState } from "react";
import { Compass, LogIn, ShieldAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { signIn, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSubmitting(false);
    }
  };

  const apiError = error instanceof ApiError ? error : null;

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-6">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Compass className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="font-extrabold text-2xl text-white tracking-wider">ATLAS</h1>
            <p className="text-[11px] uppercase tracking-widest text-cyan-400 font-semibold">
              Plataforma de empreendimentos
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-6 space-y-4">
          <div>
            <h2 className="text-sm font-bold text-white">Entrar</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Acesso restrito aos usuários da organização.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-xl border border-red-500/40 bg-red-950/30 flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <div className="text-xs text-red-200 space-y-0.5">
                <p className="font-semibold">
                  {apiError?.isOffline
                    ? "Backend do Atlas indisponível"
                    : "Não foi possível entrar"}
                </p>
                <p className="text-red-200/80">{apiError?.detail ?? error.message}</p>
              </div>
            </div>
          )}

          <label className="block">
            <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
              E-mail
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              className="w-full px-3 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
              Senha
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-3 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
            />
          </label>

          <button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="w-full px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <LogIn className="w-4 h-4" />
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="text-[11px] text-slate-500 text-center">
          Ambiente de demonstração: use as credenciais geradas por{" "}
          <code className="text-slate-400">python seed.py</code>.
        </p>
      </div>
    </div>
  );
}
