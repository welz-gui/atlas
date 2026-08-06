"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, BookOpen, ListChecks, Search, Send } from "lucide-react";
import { AIChatResponse, ApiError, sendAIChatPrompt } from "@/lib/api";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import {
  ErrorBanner,
  OnlineOnlyNotice,
} from "@/components/StateViews";

const PROMPT_SUGGESTIONS = [
  "Quais as regras de recuo frontal na zona Z2?",
  "Qual o limite de taxa de ocupação?",
  "Quais são os requisitos de permeabilidade do solo?",
  "O que o catálogo registra sobre acessibilidade?",
];

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  response?: AIChatResponse;
  timestamp: string;
}

const now = () =>
  new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

/**
 * Consulta ao catálogo regulatório.
 *
 * A página é deliberadamente explícita quanto ao que está por trás: uma busca
 * determinística, não um modelo de linguagem. O protótipo se apresentava como
 * IA e, quando a API falhava, respondia com artigos de lei inventados.
 */
export default function AssistantPage() {
  const { projects, selectedProjectId, setSelectedProjectId } = useProjects();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const send = async (promptText?: string) => {
    const text = (promptText ?? input).trim();
    if (!text || isLoading) return;

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, sender: "user", text, timestamp: now() },
    ]);
    if (!promptText) setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendAIChatPrompt(text, selectedProjectId || undefined);
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          sender: "assistant",
          text: response.answer,
          response,
          timestamp: now(),
        },
      ]);
    } catch (err) {
      // Nenhuma resposta inventada: o erro aparece como erro.
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Search className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Consulta ao catálogo regulatório
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Assistente normativo</h1>
          <p className="text-xs text-slate-400 mt-1">
            Busca determinística sobre as regras cadastradas. Não é um modelo de
            linguagem e não emite interpretação jurídica.
          </p>
        </div>

        {projects.length > 0 && (
          <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800 flex-wrap">
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedProjectId === project.id
                    ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {projectShortLabel(project)}
              </button>
            ))}
          </div>
        )}
      </div>

      <OnlineOnlyNotice feature="O assistente normativo" />
      {error && <ErrorBanner error={error} />}

      <div className="glass-panel rounded-2xl flex flex-col h-[calc(100vh-19rem)] min-h-[26rem]">
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.length === 0 && (
            <div className="text-center py-10 space-y-3">
              <BookOpen className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">
                Pergunte sobre um parâmetro cadastrado
              </p>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                O assistente responde a partir do catálogo regulatório. Se o parâmetro não
                estiver cadastrado, ele diz isso em vez de estimar uma resposta.
              </p>
            </div>
          )}

          {messages.map((message) =>
            message.sender === "user" ? (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-br-sm bg-gradient-to-r from-blue-600 to-cyan-600 text-white">
                  <p className="text-xs">{message.text}</p>
                  <p className="text-[10px] text-white/60 mt-1 text-right">
                    {message.timestamp}
                  </p>
                </div>
              </div>
            ) : (
              <div key={message.id} className="flex justify-start">
                <div className="max-w-[85%] space-y-3">
                  <div className="px-4 py-3 rounded-2xl rounded-bl-sm bg-slate-900 border border-slate-800">
                    <p className="text-xs text-slate-200 whitespace-pre-line">
                      {message.text}
                    </p>
                  </div>

                  {message.response && message.response.law_citations.length > 0 && (
                    <div className="px-4 py-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                      <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wide flex items-center gap-1.5">
                        <BookOpen className="w-3 h-3" /> Fontes no catálogo
                      </span>
                      {message.response.law_citations.map((citation, index) => (
                        <p key={index} className="text-[11px] text-slate-400">
                          • {citation}
                        </p>
                      ))}
                    </div>
                  )}

                  {message.response && message.response.suggested_actions.length > 0 && (
                    <div className="px-4 py-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                      <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wide flex items-center gap-1.5">
                        <ListChecks className="w-3 h-3" /> Próximos passos sugeridos
                      </span>
                      {message.response.suggested_actions.map((action, index) => (
                        <p key={index} className="text-[11px] text-slate-400">
                          • {action}
                        </p>
                      ))}
                    </div>
                  )}

                  {message.response && (
                    <div className="px-4 py-2.5 rounded-xl bg-amber-950/20 border border-amber-500/30 flex items-start gap-2">
                      <AlertTriangle className="w-3 h-3 text-amber-400 mt-0.5 shrink-0" />
                      <p className="text-[10px] text-amber-200/80">
                        {message.response.disclaimer}
                      </p>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-600">{message.timestamp}</p>
                </div>
              </div>
            )
          )}

          {isLoading && (
            <div className="flex justify-start">
              <div className="px-4 py-3 rounded-2xl bg-slate-900 border border-slate-800">
                <p className="text-xs text-slate-400 animate-pulse">
                  Consultando o catálogo...
                </p>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        <div className="p-4 border-t border-slate-800 space-y-3">
          {messages.length === 0 && (
            <div className="flex flex-wrap gap-2">
              {PROMPT_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => send(suggestion)}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 hover:border-cyan-500/40 hover:text-white transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
            className="flex items-center gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Pergunte sobre um parâmetro urbanístico cadastrado..."
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
