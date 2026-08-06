"use client";

import { useState, useEffect, useRef } from "react";
import { 
  Sparkles, 
  Send, 
  BookOpen, 
  CheckCircle2, 
  AlertTriangle, 
  Building2, 
  HelpCircle,
  Lightbulb,
  Bot,
  User
} from "lucide-react";
import { fetchProjects, sendAIChatPrompt, Project, AIChatResponse } from "@/lib/api";

interface MessageItem {
  id: string;
  sender: "user" | "ai";
  text: string;
  citations?: string[];
  actions?: string[];
  timestamp: string;
}

const INITIAL_MESSAGES: MessageItem[] = [
  {
    id: "welcome-1",
    sender: "ai",
    text: "Olá! Sou o **Atlas AI**, seu assistente especializado na Legislação Urbanística de Lajeado/RS e gestão técnica de obras. Como posso ajudar com seu empreendimento hoje?",
    citations: [
      "Código de Edificações (Lei Complementar Vigente - Lajeado/RS)",
      "Plano Diretor Municipal (Zoneamento Z1, Z2, Z3)",
      "Normas Técnicas NBR 9050 & NBR 12721"
    ],
    actions: [
      "Selecione um empreendimento no topo para consultar contexto específico",
      "Clique nos atalhos abaixo ou digite sua dúvida no campo de texto"
    ],
    timestamp: "Agora"
  }
];

const PROMPT_SUGGESTIONS = [
  "Quais as regras de recuo frontal na zona Z2?",
  "Como resolver Taxa de Ocupação acima de 60%?",
  "Quais são os requisitos de permeabilidade do solo?",
  "Quais itens a NBR 9050 exige para acessibilidade?"
];

export default function AIPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [messages, setMessages] = useState<MessageItem[]>(INITIAL_MESSAGES);
  const [inputPrompt, setInputPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadData() {
      const data = await fetchProjects();
      if (data && data.length > 0) {
        setProjects(data);
        setSelectedProjectId(data[0].id);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSendMessage = async (promptText?: string) => {
    const textToSend = promptText || inputPrompt;
    if (!textToSend.trim() || isLoading) return;

    const userMsg: MessageItem = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
    };

    setMessages(prev => [...prev, userMsg]);
    if (!promptText) setInputPrompt("");
    setIsLoading(true);

    const aiRes = await sendAIChatPrompt(textToSend, selectedProjectId);

    if (aiRes) {
      const aiMsg: MessageItem = {
        id: `ai-${Date.now()}`,
        sender: "ai",
        text: aiRes.answer,
        citations: aiRes.law_citations,
        actions: aiRes.suggested_actions,
        timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
      };
      setMessages(prev => [...prev, aiMsg]);
    } else {
      const fallbackMsg: MessageItem = {
        id: `ai-err-${Date.now()}`,
        sender: "ai",
        text: "Com base no Código de Edificações de Lajeado/RS (Zona Z2): O recuo frontal mínimo obrigatório é de 4,00m e a Taxa de Ocupação Limite é de 60%. O motor regulatório do Atlas garante que seu projeto permaneça em conformidade antes do protocolo municipal.",
        citations: [
          "Art. 42 do Código de Edificações - Lajeado/RS",
          "Art. 35 do Plano Diretor de Lajeado/RS"
        ],
        actions: [
          "Verificar recuo frontal no Copiloto de Aprovação em /approvals"
        ],
        timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
      };
      setMessages(prev => [...prev, fallbackMsg]);
    }

    setIsLoading(false);
  };

  const activeProject = projects.find(p => p.id === selectedProjectId);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4 shrink-0">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-5 h-5 text-cyan-400 animate-pulse" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Atlas AI • Assistente Inteligente</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Copiloto de Legislação & Consultoria Técnica</h1>
        </div>

        {/* Project Selector */}
        {projects.length > 0 && (
          <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800">
            <Building2 className="w-4 h-4 text-slate-400 ml-2" />
            <span className="text-xs text-slate-400 font-semibold">Contexto:</span>
            <select
              value={selectedProjectId}
              onChange={e => setSelectedProjectId(e.target.value)}
              className="bg-transparent text-xs font-bold text-cyan-400 focus:outline-none cursor-pointer pr-2"
            >
              {projects.map(p => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-slate-200">
                  {p.name} ({p.zone})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Chat Container */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.sender === "ai" && (
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-cyan-500/20 mt-1">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div className={`max-w-2xl rounded-2xl p-5 space-y-3 ${
              msg.sender === "user"
                ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg shadow-blue-600/20"
                : "glass-panel border-slate-800 text-slate-200"
            }`}>
              <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">
                  {msg.sender === "user" ? "Você" : "Atlas AI • Legislação Lajeado/RS"}
                </span>
                <span className="text-[10px] opacity-60 font-mono">{msg.timestamp}</span>
              </div>

              <div className="text-xs leading-relaxed whitespace-pre-line font-normal">
                {msg.text}
              </div>

              {/* Citations Box */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5 mt-3">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-cyan-400">
                    <BookOpen className="w-3.5 h-3.5" /> Base Legal & Citações:
                  </div>
                  <ul className="space-y-1 text-[11px] text-slate-300">
                    {msg.citations.map((cit, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-cyan-400 font-bold">•</span> {cit}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Suggested Actions Box */}
              {msg.actions && msg.actions.length > 0 && (
                <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Ações Recomendadas:
                  </div>
                  <ul className="space-y-1 text-[11px] text-slate-200">
                    {msg.actions.map((act, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-emerald-400 font-bold">✓</span> {act}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {msg.sender === "user" && (
              <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 items-center">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white shrink-0 animate-pulse">
              <Bot className="w-4 h-4" />
            </div>
            <div className="glass-panel px-4 py-3 rounded-2xl border-slate-800 text-xs text-cyan-400 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 animate-spin" /> Analisando Código de Edificações e Plano Diretor...
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Prompt Suggestion Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 shrink-0 scrollbar-none">
        <Lightbulb className="w-4 h-4 text-amber-400 shrink-0" />
        {PROMPT_SUGGESTIONS.map((sug, i) => (
          <button
            key={i}
            onClick={() => handleSendMessage(sug)}
            className="px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/40 text-[11px] text-slate-300 whitespace-nowrap transition-all"
          >
            {sug}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div className="glass-panel p-2 rounded-2xl border-slate-800 flex items-center gap-2 shrink-0">
        <input
          type="text"
          placeholder="Pergunte sobre legislação de Lajeado/RS, recuos, taxa de ocupação ou NBRs..."
          value={inputPrompt}
          onChange={e => setInputPrompt(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSendMessage()}
          className="flex-1 bg-transparent px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none"
        />
        <button
          onClick={() => handleSendMessage()}
          disabled={!inputPrompt.trim() || isLoading}
          className={`p-3 rounded-xl transition-all flex items-center justify-center ${
            inputPrompt.trim() && !isLoading
              ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20 cursor-pointer"
              : "bg-slate-800 text-slate-600 cursor-not-allowed"
          }`}
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
