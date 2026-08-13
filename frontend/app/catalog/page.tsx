"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  History,
  ExternalLink,
  Plus,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  X,
} from "lucide-react";
import {
  ApiError,
  RegulatoryDocument,
  RegulatoryRule,
  RuleValidationEvent,
  createRegulatoryDocument,
  discoverRegulatoryDocuments,
  fetchCatalogRules,
  fetchRegulatoryDocuments,
  fetchRuleEvents,
  humanize,
  validateRule,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import {
  EmptyState,
  ErrorBanner,
  LoadingState,
  OnlineOnlyNotice,
} from "@/components/StateViews";

const STATE_STYLE: Record<string, string> = {
  vigente: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  em_validacao: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  rascunho_extraido_por_ia: "bg-slate-800 text-slate-400 border-slate-700",
  suspensa: "bg-blue-500/10 text-blue-300 border-blue-500/40",
  revogada: "bg-red-500/10 text-red-400 border-red-500/30",
  substituida: "bg-slate-800 text-slate-400 border-slate-700",
};

/** Ações oferecidas por estado — espelha ALLOWED_TRANSITIONS do backend. */
const ACTIONS_BY_STATE: Record<string, { action: string; label: string }[]> = {
  em_validacao: [
    { action: "publicar", label: "Publicar" },
    { action: "rejeitar", label: "Devolver a rascunho" },
    { action: "revogar", label: "Revogar" },
  ],
  rascunho_extraido_por_ia: [
    { action: "reabrir", label: "Enviar para validação" },
    { action: "revogar", label: "Revogar" },
  ],
  vigente: [
    { action: "suspender", label: "Suspender" },
    { action: "revogar", label: "Revogar" },
  ],
  suspensa: [
    { action: "reabrir", label: "Reabrir validação" },
    { action: "revogar", label: "Revogar" },
  ],
  revogada: [],
  substituida: [],
};

export default function CatalogPage() {
  const { can } = useAuth();
  const canValidate = can("catalog:validate");
  const {
    projects,
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    isLoading: projectsLoading,
  } = useProjects();

  const [rules, setRules] = useState<RegulatoryRule[]>([]);
  const [documents, setDocuments] = useState<RegulatoryDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [filter, setFilter] = useState<"pendentes" | "todas">("pendentes");
  const [selected, setSelected] = useState<RegulatoryRule | null>(null);
  const [isDocumentModalOpen, setIsDocumentModalOpen] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryMessage, setDiscoveryMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [allRules, docs] = await Promise.all([
        fetchCatalogRules(
          selectedProject ? { jurisdiction: selectedProject.city_ibge } : undefined
        ),
        fetchRegulatoryDocuments(selectedProject?.city_ibge),
      ]);
      setRules(allRules);
      setDocuments(docs);
    } catch (err) {
      setRules([]);
      setDocuments([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [selectedProject]);

  useEffect(() => {
    load();
  }, [load]);

  const visible =
    filter === "todas"
      ? rules
      : rules.filter((r) => !r.is_publishable && r.state !== "revogada");

  const publishable = rules.filter((r) => r.is_publishable).length;
  const discoveredDocuments = documents.filter((document) => document.state === "descoberto");

  const handleDiscovery = async () => {
    if (!selectedProject) {
      setError(new Error("Selecione um empreendimento para definir o município."));
      return;
    }
    setIsDiscovering(true);
    setError(null);
    setDiscoveryMessage(null);
    try {
      const submission = await discoverRegulatoryDocuments(
        selectedProject.city_ibge,
        selectedProject.id
      );
      if (submission.job.status === "falhou") {
        throw new Error(submission.job.error || "A busca automática falhou.");
      }
      if (submission.job.result) {
        const result = submission.job.result;
        setDiscoveryMessage(
          `${result.candidates_found} candidato(s) localizado(s): ${result.created} novo(s), ${result.updated} atualizado(s). Todos aguardam conferência humana.`
        );
        await load();
      } else {
        setDiscoveryMessage(
          "Busca enfileirada. O resultado aparecerá no catálogo após a conclusão do worker."
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ScrollText className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Subsistema de operação regulatória
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Catálogo de regras</h1>
          <p className="text-xs text-slate-400 mt-1">
            Uma regra só pode constar de laudo entregue ao cliente depois de conferida
            contra o texto legal por um responsável identificado.
          </p>
        </div>

        {canValidate && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleDiscovery}
              disabled={isDiscovering}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-xs flex items-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isDiscovering ? "animate-spin" : ""}`} />
              {isDiscovering ? "Buscando..." : "Buscar normas oficiais"}
            </button>
            <button
              onClick={() => setIsDocumentModalOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-cyan-500/40 text-slate-200 font-semibold text-xs flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> Cadastrar norma
            </button>
          </div>
        )}
      </div>

      <OnlineOnlyNotice feature="A validação do catálogo" />
      <div className="glass-panel rounded-2xl p-4 flex flex-col md:flex-row md:items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-white">Escopo do empreendimento</p>
          <p className="text-[11px] text-slate-400 mt-1">
            O Atlas considera Brasil, estado e o município deste projeto. Normas de
            outro município ficam fora da análise.
          </p>
        </div>
        <select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          disabled={projectsLoading || projects.length === 0}
          className="min-w-64 px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:border-cyan-500 outline-none disabled:opacity-50"
        >
          {projects.length === 0 && <option value="">Nenhum empreendimento</option>}
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {projectShortLabel(project)} — {project.city_name}/{project.state}
            </option>
          ))}
        </select>
      </div>
      {error && <ErrorBanner error={error} onRetry={load} />}
      {discoveryMessage && (
        <div className="p-4 rounded-xl border border-cyan-500/30 bg-cyan-950/20 text-xs text-cyan-100">
          {discoveryMessage}
        </div>
      )}
      {isLoading && <LoadingState label="Carregando catálogo..." />}

      {!isLoading && !error && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            <Metric label="Regras no catálogo" value={rules.length} accent="border-l-cyan-500" />
            <Metric
              label="Publicáveis"
              value={publishable}
              accent="border-l-emerald-500"
              valueClass="text-emerald-400"
            />
            <Metric
              label="Aguardando validação"
              value={rules.filter((r) => !r.is_publishable && r.state !== "revogada").length}
              accent="border-l-amber-500"
              valueClass="text-amber-400"
            />
            <Metric
              label="Normas catalogadas"
              value={documents.length}
              accent="border-l-blue-500"
              valueClass="text-blue-300"
            />
          </div>

          {publishable === 0 && rules.length > 0 && (
            <div className="p-4 rounded-2xl border border-amber-500/40 bg-amber-950/20 flex items-start gap-3">
              <ShieldAlert className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-xs text-amber-200/90">
                <span className="font-bold text-amber-300">
                  Nenhuma regra publicada.
                </span>{" "}
                Enquanto o catálogo não for validado, todo laudo sai marcado como uso
                interno e não deve ser entregue ao cliente.
              </p>
            </div>
          )}

          {discoveredDocuments.length > 0 && (
            <div className="glass-panel rounded-2xl p-5 space-y-3">
              <div>
                <h2 className="text-sm font-bold text-white">Normas descobertas</h2>
                <p className="text-[11px] text-slate-400 mt-1">
                  Candidatos vindos de índices oficiais. Nenhum deles alimenta o copiloto até ser conferido.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {discoveredDocuments.map((document) => (
                  <a
                    key={document.id}
                    href={document.url ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/30 flex items-start justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-200">{document.title}</p>
                      <p className="text-[10px] text-slate-500 mt-1">
                        {document.theme || humanize(document.doc_type)} · aguardando conferência
                      </p>
                    </div>
                    <ExternalLink className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  </a>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800 w-fit">
            {(["pendentes", "todas"] as const).map((option) => (
              <button
                key={option}
                onClick={() => setFilter(option)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                  filter === option
                    ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {option}
              </button>
            ))}
          </div>

          {visible.length === 0 ? (
            <EmptyState
              title={
                filter === "pendentes"
                  ? "Nenhuma regra aguardando validação"
                  : "Catálogo vazio"
              }
              description={
                filter === "pendentes"
                  ? "Todas as regras do catálogo já foram conferidas e publicadas."
                  : "Importe o catálogo de semente pelo backend para começar."
              }
            />
          ) : (
            <div className="space-y-3">
              {visible.map((rule) => (
                <div
                  key={rule.id}
                  className="glass-panel rounded-2xl p-5 space-y-3 cursor-pointer hover:border-cyan-500/30 transition-all"
                  onClick={() => setSelected(rule)}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-white">{rule.title}</h3>
                      <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                        {rule.rule_key} • {rule.jurisdiction}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${
                          STATE_STYLE[rule.state] ?? STATE_STYLE.substituida
                        }`}
                      >
                        {humanize(rule.state)}
                      </span>
                      {rule.is_publishable && (
                        <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" /> publicável
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <Field
                      label="Fonte legal"
                      value={
                        rule.source_article
                          ? `${rule.source_document_label ?? "—"}, ${rule.source_article}`
                          : `${rule.source_document_label ?? "—"} (artigo não conferido)`
                      }
                      warn={!rule.source_article}
                    />
                    <Field
                      label="Validado por"
                      value={rule.validated_by_name ?? "pendente"}
                      warn={!rule.validated_by_name}
                    />
                    <Field label="Severidade" value={humanize(rule.severity)} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {selected && (
        <RuleDetailModal
          rule={selected}
          documents={documents}
          canValidate={canValidate}
          onClose={() => setSelected(null)}
          onValidated={(updated) => {
            setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
            setSelected(updated);
          }}
        />
      )}

      {isDocumentModalOpen && (
        <DocumentModal
          onClose={() => setIsDocumentModalOpen(false)}
          onCreated={(doc) => {
            setDocuments((prev) => [...prev, doc]);
            setIsDocumentModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  accent,
  valueClass = "text-white",
}: {
  label: string;
  value: number;
  accent: string;
  valueClass?: string;
}) {
  return (
    <div className={`glass-panel p-5 rounded-2xl border-l-4 ${accent}`}>
      <p className="text-[11px] font-bold text-slate-400 uppercase">{label}</p>
      <p className={`text-2xl font-extrabold mt-1 ${valueClass}`}>{value}</p>
    </div>
  );
}

function Field({
  label,
  value,
  warn,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div>
      <span className="text-slate-500 text-[11px] block">{label}:</span>
      <span className={warn ? "text-amber-400 font-semibold" : "text-slate-200"}>
        {value}
      </span>
    </div>
  );
}

function RuleDetailModal({
  rule,
  documents,
  canValidate,
  onClose,
  onValidated,
}: {
  rule: RegulatoryRule;
  documents: RegulatoryDocument[];
  canValidate: boolean;
  onClose: () => void;
  onValidated: (rule: RegulatoryRule) => void;
}) {
  const [events, setEvents] = useState<RuleValidationEvent[]>([]);
  const [documentId, setDocumentId] = useState(rule.source_document_id ?? "");
  const [article, setArticle] = useState(rule.source_article ?? "");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    fetchRuleEvents(rule.id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [rule.id]);

  const actions = ACTIONS_BY_STATE[rule.state] ?? [];

  const handleAction = async (action: string) => {
    setIsSaving(true);
    setError(null);
    try {
      const updated = await validateRule(rule.id, {
        action: action as "publicar",
        notes: notes || undefined,
        source_document_id: documentId || undefined,
        source_article: article || undefined,
      });
      onValidated(updated);
      setEvents(await fetchRuleEvents(rule.id));
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
      <div className="glass-panel rounded-2xl p-6 w-full max-w-2xl space-y-5 my-8">
        <div className="flex items-start justify-between border-b border-slate-800 pb-4 gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-white">{rule.title}</h2>
            <p className="text-[11px] text-slate-500 font-mono mt-0.5">{rule.rule_key}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <div className="grid grid-cols-2 gap-3 text-xs">
          <Field label="Estado" value={humanize(rule.state)} />
          <Field label="Severidade" value={humanize(rule.severity)} />
          <Field
            label="Limite verificado"
            value={
              rule.check
                ? `${rule.check.field} ${rule.check.operator} ${rule.check.value} ${
                    rule.check.unit ?? ""
                  }`
                : "análise documental"
            }
          />
          <Field
            label="Evidência exigida"
            value={rule.evidence_required.join(", ") || "—"}
          />
        </div>

        {rule.notes && (
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <p className="text-[11px] text-slate-400">{rule.notes}</p>
          </div>
        )}

        {canValidate && actions.length > 0 && (
          <div className="space-y-3 pt-3 border-t border-slate-800">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-white">Ato de validação técnica</h3>
            </div>
            <p className="text-[11px] text-amber-200/80">
              Publicar exige documento de origem <strong>e</strong> artigo conferido no
              texto legal. Sem isso, a fonte permanece não verificada.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <select
                value={documentId}
                onChange={(e) => setDocumentId(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white outline-none"
              >
                <option value="">Documento de origem...</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title}
                  </option>
                ))}
              </select>
              <input
                value={article}
                onChange={(e) => setArticle(e.target.value)}
                placeholder="Artigo conferido (ex.: Art. 45)"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:border-cyan-500 outline-none"
              />
            </div>

            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Observações da conferência (opcional)"
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:border-cyan-500 outline-none"
            />

            <div className="flex flex-wrap gap-2">
              {actions.map(({ action, label }) => (
                <button
                  key={action}
                  onClick={() => handleAction(action)}
                  disabled={isSaving}
                  className={`px-3 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 ${
                    action === "publicar"
                      ? "bg-gradient-to-r from-emerald-500 to-cyan-600 text-white"
                      : "bg-slate-900 border border-slate-800 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {!canValidate && (
          <p className="text-[11px] text-slate-500 pt-3 border-t border-slate-800">
            Somente usuários com papel de validador técnico podem publicar regras.
          </p>
        )}

        <div className="space-y-2 pt-3 border-t border-slate-800">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-slate-500" />
            <h3 className="text-xs font-bold text-white">Histórico de validação</h3>
          </div>
          {events.length === 0 ? (
            <p className="text-[11px] text-slate-500">Nenhum ato registrado.</p>
          ) : (
            events.map((event) => (
              <div
                key={event.id}
                className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px]"
              >
                <p className="text-slate-300">
                  <span className="font-semibold text-cyan-400">{event.action}</span>{" "}
                  {humanize(event.from_state)} → {humanize(event.to_state)}
                </p>
                <p className="text-slate-500 mt-0.5">
                  {event.actor_name ?? "—"} •{" "}
                  {new Date(event.created_at).toLocaleString("pt-BR")}
                </p>
                {event.notes && <p className="text-slate-400 mt-1">{event.notes}</p>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (doc: RegulatoryDocument) => void;
}) {
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("lei");
  const [number, setNumber] = useState("");
  const [issuingBody, setIssuingBody] = useState("");
  const [url, setUrl] = useState("");
  const [jurisdiction, setJurisdiction] = useState("BR-RS-4311403");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      onCreated(
        await createRegulatoryDocument({
          jurisdiction,
          title,
          doc_type: docType,
          number: number || undefined,
          issuing_body: issuingBody || undefined,
          url: url || undefined,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-4"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Cadastrar norma</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Título (ex.: Plano Diretor de Lajeado)"
          required
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />
        <div className="grid grid-cols-2 gap-3">
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white outline-none"
          >
            <option value="lei">Lei</option>
            <option value="lei_complementar">Lei complementar</option>
            <option value="plano_diretor">Plano diretor</option>
            <option value="codigo_edificacoes">Código de edificações</option>
            <option value="decreto">Decreto</option>
            <option value="norma_tecnica">Norma técnica</option>
          </select>
          <input
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="Número"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
          />
        </div>
        <input
          value={jurisdiction}
          onChange={(e) => setJurisdiction(e.target.value)}
          placeholder="Jurisdição (código IBGE)"
          required
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />
        <input
          value={issuingBody}
          onChange={(e) => setIssuingBody(e.target.value)}
          placeholder="Órgão emissor"
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="URL da fonte oficial"
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
        />

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 text-xs font-semibold"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-50"
          >
            {isSaving ? "Salvando..." : "Cadastrar"}
          </button>
        </div>
      </form>
    </div>
  );
}
