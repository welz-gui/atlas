"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  FileText,
  Hash,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import {
  ApiError,
  DocumentItem,
  ExtractionResponse,
  Project,
  extractDocumentParameters,
  fetchProjectDocuments,
  updateProjectParameters,
  uploadProjectDocument,
} from "@/lib/api";
import { projectShortLabel, useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

const EXTRACTION_FIELDS: { key: keyof ExtractionResponse["extracted_parameters"]; label: string; unit: string }[] = [
  { key: "lot_area", label: "Área do lote", unit: "m²" },
  { key: "built_area", label: "Área construída", unit: "m²" },
  { key: "front_setback", label: "Recuo frontal", unit: "m" },
  { key: "rear_setback", label: "Recuo dos fundos", unit: "m" },
  { key: "permeability_rate", label: "Permeabilidade", unit: "%" },
  { key: "floors", label: "Pavimentos", unit: "" },
];

export default function DocumentsPage() {
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    replaceProject,
    isLoading: isLoadingProjects,
    error: projectsError,
    reload: reloadProjects,
  } = useProjects();

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<ApiError | Error | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [extractionError, setExtractionError] = useState<ApiError | Error | null>(null);
  const [isApplied, setIsApplied] = useState(false);

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("projeto_arquitetonico");
  const [version, setVersion] = useState("v1.0");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!selectedProjectId) {
      setDocuments([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setDocuments(await fetchProjectDocuments(selectedProjectId));
    } catch (err) {
      setDocuments([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadDocuments();
    setExtraction(null);
    setExtractionError(null);
  }, [loadDocuments]);

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedFile || !selectedProjectId || !title) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("category", category);
      formData.append("version", version);
      formData.append("file", selectedFile);

      const uploaded = await uploadProjectDocument(selectedProjectId, formData);
      setDocuments((prev) => [uploaded, ...prev]);
      setTitle("");
      setSelectedFile(null);
    } catch (err) {
      // Sem documento no servidor não há documento na lista. O protótipo
      // inseria uma entrada local com um hash fixo, dando a impressão de um
      // upload que nunca aconteceu.
      setUploadError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsUploading(false);
    }
  };

  const handleExtract = async (documentId: string) => {
    if (!selectedProjectId) return;
    setExtractingId(documentId);
    setExtraction(null);
    setExtractionError(null);
    setIsApplied(false);
    try {
      setExtraction(await extractDocumentParameters(selectedProjectId, documentId));
    } catch (err) {
      setExtractionError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setExtractingId(null);
    }
  };

  const handleApplyExtracted = async () => {
    if (!extraction || !selectedProjectId) return;
    const parameters = extraction.extracted_parameters;

    // Só o que foi efetivamente extraído é aplicado; campos nulos ficam como
    // "não informado" no cadastro.
    const payload: Partial<Project> = {};
    for (const { key } of EXTRACTION_FIELDS) {
      const value = parameters[key];
      if (value !== null && value !== undefined) {
        (payload as Record<string, number>)[key] = value;
      }
    }
    if (Object.keys(payload).length === 0) return;

    try {
      const updated = await updateProjectParameters(selectedProjectId, payload);
      replaceProject(updated);
      setIsApplied(true);
    } catch (err) {
      setExtractionError(err instanceof Error ? err : new Error(String(err)));
    }
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const appliedCount = extraction
    ? EXTRACTION_FIELDS.filter(
        ({ key }) => extraction.extracted_parameters[key] !== null
      ).length
    : 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Módulo documental
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">
            Gestão documental e extração assistida
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Cada upload recebe hash SHA-256. A extração devolve apenas o que estiver
            escrito no documento — nunca um valor estimado.
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

      {projectsError && <ErrorBanner error={projectsError} onRetry={reloadProjects} />}
      {error && <ErrorBanner error={error} onRetry={loadDocuments} />}
      {(isLoadingProjects || isLoading) && <LoadingState label="Carregando documentos..." />}

      {!isLoadingProjects && !projectsError && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre um empreendimento para anexar documentos e pranchas."
        />
      )}

      {selectedProjectId && !isLoading && (
        <>
          <div className="glass-panel rounded-2xl p-6 border-cyan-500/30 glow-blue space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <UploadCloud className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-bold text-white">
                Upload de prancha ou documento de projeto
              </h2>
            </div>

            {uploadError && <ErrorBanner error={uploadError} />}

            <form onSubmit={handleUpload} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <label className="block">
                  <span className="block font-semibold text-slate-300 mb-1">Título:</span>
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white focus:border-cyan-500 outline-none"
                  />
                </label>
                <label className="block">
                  <span className="block font-semibold text-slate-300 mb-1">Categoria:</span>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white outline-none"
                  >
                    <option value="projeto_arquitetonico">Projeto arquitetônico</option>
                    <option value="memorial">Memorial descritivo</option>
                    <option value="levantamento">Levantamento topográfico</option>
                    <option value="matricula">Matrícula do imóvel</option>
                    <option value="outros">Outros</option>
                  </select>
                </label>
                <label className="block">
                  <span className="block font-semibold text-slate-300 mb-1">Versão:</span>
                  <input
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white focus:border-cyan-500 outline-none"
                  />
                </label>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <input
                  type="file"
                  onChange={(e) => {
                    const file = e.target.files?.[0] ?? null;
                    setSelectedFile(file);
                    if (file && !title) setTitle(file.name.replace(/\.[^/.]+$/, ""));
                  }}
                  className="text-xs text-slate-400 file:mr-3 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-slate-800 file:text-slate-200 file:text-xs file:font-semibold"
                />
                <button
                  type="submit"
                  disabled={isUploading || !selectedFile}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isUploading ? "Enviando..." : "Enviar documento"}
                </button>
              </div>
            </form>
          </div>

          {extractionError && <ErrorBanner error={extractionError} />}

          {extraction && (
            <div className="glass-panel rounded-2xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <h2 className="text-sm font-bold text-white">
                    Extração assistida: {extraction.document_title}
                  </h2>
                </div>
                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${
                    extraction.status === "extraido"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : extraction.status === "extraido_parcial"
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                      : "bg-blue-500/10 text-blue-300 border-blue-500/40"
                  }`}
                >
                  {extraction.status.replace(/_/g, " ")} · {extraction.fields_found} de{" "}
                  {extraction.fields_expected}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                {EXTRACTION_FIELDS.map(({ key, label, unit }) => {
                  const value = extraction.extracted_parameters[key];
                  return (
                    <div key={key}>
                      <span className="text-slate-500 text-[11px] block">{label}:</span>
                      {value === null || value === undefined ? (
                        <span className="font-mono text-blue-300/70 italic">
                          não encontrado
                        </span>
                      ) : (
                        <span className="font-mono text-cyan-400 font-bold">
                          {value} {unit}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              {extraction.evidence.length > 0 && (
                <div className="space-y-1.5 pt-3 border-t border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase">
                    Evidência (trecho de origem)
                  </span>
                  {extraction.evidence.map((item, index) => (
                    <p key={index} className="text-[11px] text-slate-300 font-mono">
                      • {item}
                    </p>
                  ))}
                </div>
              )}

              {extraction.warnings.length > 0 && (
                <div className="p-3 rounded-xl border border-blue-500/40 bg-blue-950/20 space-y-1">
                  <span className="text-[11px] font-bold text-blue-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> Avisos da extração
                  </span>
                  {extraction.warnings.map((warning, index) => (
                    <p key={index} className="text-[11px] text-blue-200/80">
                      {warning}
                    </p>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between pt-3 border-t border-slate-800 gap-3 flex-wrap">
                <p className="text-[11px] text-slate-400">
                  {appliedCount === 0
                    ? "Nada a aplicar: nenhum parâmetro foi localizado no documento."
                    : `${appliedCount} parâmetro(s) serão gravados no cadastro. Os demais permanecem "não informado".`}
                </p>
                <button
                  onClick={handleApplyExtracted}
                  disabled={appliedCount === 0 || isApplied}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isApplied ? (
                    <>
                      <Check className="w-3.5 h-3.5" /> Aplicado
                    </>
                  ) : (
                    "Aplicar ao cadastro"
                  )}
                </button>
              </div>
            </div>
          )}

          <div className="glass-panel rounded-2xl p-6 space-y-4">
            <h2 className="text-base font-bold text-white border-b border-slate-800 pb-4">
              Documentos do empreendimento
            </h2>

            {documents.length === 0 ? (
              <EmptyState
                title="Nenhum documento anexado"
                description="Envie a prancha arquitetônica ou o memorial descritivo para iniciar a extração assistida."
              />
            ) : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-white truncate">{doc.title}</p>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          {doc.category.replace(/_/g, " ")} • {doc.version}
                          {doc.original_filename && ` • ${doc.original_filename}`}
                          {doc.size_bytes &&
                            ` • ${(doc.size_bytes / 1024).toFixed(0)} KB`}
                        </p>
                      </div>

                      <button
                        onClick={() => handleExtract(doc.id)}
                        disabled={extractingId === doc.id}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 shrink-0 disabled:opacity-50"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                        {extractingId === doc.id ? "Extraindo..." : "Extrair parâmetros"}
                      </button>
                    </div>

                    {doc.hash_sha256 && (
                      <button
                        onClick={() => handleCopyHash(doc.hash_sha256!)}
                        className="w-full flex items-center gap-2 p-2 rounded-lg bg-slate-950/60 border border-slate-800 text-left group"
                      >
                        <Hash className="w-3 h-3 text-cyan-400 shrink-0" />
                        <span className="text-[10px] font-mono text-slate-400 truncate flex-1">
                          {doc.hash_sha256}
                        </span>
                        {copiedHash === doc.hash_sha256 ? (
                          <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                        ) : (
                          <Copy className="w-3 h-3 text-slate-500 group-hover:text-slate-300 shrink-0" />
                        )}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
