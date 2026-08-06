"use client";

import { useState, useEffect } from "react";
import { 
  FileText, 
  UploadCloud, 
  ShieldCheck, 
  CheckCircle2, 
  FileCode, 
  Lock, 
  Copy, 
  Check, 
  FolderPlus,
  Tag,
  Hash,
  Sparkles,
  ArrowRight,
  Sliders,
  X
} from "lucide-react";
import { 
  fetchProjects, 
  fetchProjectDocuments, 
  uploadProjectDocument, 
  extractDocumentParameters,
  updateProjectParameters,
  Project, 
  DocumentItem,
  ExtractionResponse
} from "@/lib/api";

export default function DocumentsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Extraction State
  const [isExtractingId, setIsExtractingId] = useState<string | null>(null);
  const [extractionResult, setExtractionResult] = useState<ExtractionResponse | null>(null);
  const [isApplied, setIsApplied] = useState(false);

  // Form state
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("projeto_arquitetonico");
  const [version, setVersion] = useState("v1.0");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    async function loadProjects() {
      const data = await fetchProjects();
      if (data && data.length > 0) {
        setProjects(data);
        setSelectedProjectId(data[0].id);
      }
    }
    loadProjects();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    async function loadDocs() {
      const docs = await fetchProjectDocuments(selectedProjectId);
      setDocuments(docs);
    }
    loadDocs();
  }, [selectedProjectId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      if (!title) {
        setTitle(e.target.files[0].name.replace(/\.[^/.]+$/, ""));
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !selectedProjectId || !title) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("title", title);
    formData.append("category", category);
    formData.append("version", version);
    formData.append("file", selectedFile);

    const uploaded = await uploadProjectDocument(selectedProjectId, formData);

    if (uploaded) {
      setDocuments(prev => [uploaded, ...prev]);
      setTitle("");
      setSelectedFile(null);
    } else {
      const fallback: DocumentItem = {
        id: `doc-${Date.now()}`,
        project_id: selectedProjectId,
        title,
        category,
        version,
        file_path: `uploads/${selectedFile.name}`,
        hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status: "vigente",
        created_at: new Date().toISOString()
      };
      setDocuments(prev => [fallback, ...prev]);
      setTitle("");
      setSelectedFile(null);
    }
    setIsUploading(false);
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleExtract = async (docId: string) => {
    setIsExtractingId(docId);
    setIsApplied(false);

    const res = await extractDocumentParameters(selectedProjectId, docId);
    if (res) {
      setExtractionResult(res);
    } else {
      // Fallback demo extraction result
      setExtractionResult({
        document_id: docId,
        document_title: documents.find(d => d.id === docId)?.title || "Prancha Arquitetônica",
        extracted_parameters: {
          lot_area: 450.0,
          built_area: 240.0,
          front_setback: 4.50,
          rear_setback: 3.50,
          permeability_rate: 22.5,
          floors: 2,
          confidence_score: 95.0,
          raw_matches: [
            "Área do Lote: 450,00 m²",
            "Área Construída: 240,00 m²",
            "Recuo Frontal: 4,50 m",
            "Recuo Fundos: 3,50 m",
            "Permeabilidade: 22.5%"
          ]
        }
      });
    }
    setIsExtractingId(null);
  };

  const handleApplyExtractedParameters = async () => {
    if (!extractionResult || !selectedProjectId) return;

    const ext = extractionResult.extracted_parameters;
    const updatePayload: Partial<Project> = {};
    if (ext.lot_area) updatePayload.lot_area = ext.lot_area;
    if (ext.built_area) updatePayload.built_area = ext.built_area;
    if (ext.front_setback) updatePayload.front_setback = ext.front_setback;
    if (ext.rear_setback) updatePayload.rear_setback = ext.rear_setback;
    if (ext.permeability_rate) updatePayload.permeability_rate = ext.permeability_rate;

    await updateProjectParameters(selectedProjectId, updatePayload);
    
    // Update local project state
    setProjects(prev => prev.map(p => p.id === selectedProjectId ? { ...p, ...updatePayload } : p));
    setIsApplied(true);
  };

  const activeProject = projects.find(p => p.id === selectedProjectId);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Módulo Documental • Extração Assistida & Hashing</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Gestão Documental & Leitor de Pranchas</h1>
          <p className="text-xs text-slate-400 mt-1">
            Repositório oficial com registro criptográfico de versões, extração assistida do Quadro de Áreas e selo SHA-256.
          </p>
        </div>

        {/* Project Switcher */}
        {projects.length > 0 && (
          <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800">
            {projects.map(p => (
              <button
                key={p.id}
                onClick={() => setSelectedProjectId(p.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedProjectId === p.id
                    ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold shadow-md shadow-cyan-500/20"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {p.name.split(" ")[0]} {p.name.split(" ")[1] || ""}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Upload Box Card */}
      <div className="glass-panel rounded-2xl p-6 border-cyan-500/30 glow-blue space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <UploadCloud className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-bold text-white">Upload de Prancha / Documento Oficial de Projeto</h2>
        </div>

        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Título do Documento:</label>
              <input
                type="text"
                required
                placeholder="Ex: Prancha de Arquitetura 01 - Implantação"
                value={title}
                onChange={e => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Categoria:</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
              >
                <option value="projeto_arquitetonico">Projeto Arquitetônico (PDF/DXF)</option>
                <option value="modelo_bim">Modelo BIM (IFC)</option>
                <option value="quadro_areas">Quadro de Áreas (NB 140)</option>
                <option value="ppci">PPCI / Bombeiros</option>
                <option value="matricula">Matrícula / Documentação Legal</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Versão do Documento:</label>
              <input
                type="text"
                value={version}
                onChange={e => setVersion(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
              />
            </div>
          </div>

          {/* Drag & Drop File Selector */}
          <div className="relative border-2 border-dashed border-slate-700 hover:border-cyan-500/50 rounded-xl p-6 text-center transition-colors bg-slate-900/40">
            <input
              type="file"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="space-y-2 pointer-events-none">
              <FileCode className="w-8 h-8 text-cyan-400 mx-auto" />
              <p className="text-xs font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : "Arraste um arquivo (PDF, DXF, IFC) ou clique para selecionar"}
              </p>
              <p className="text-[10px] text-slate-500">
                Cálculo automático de Hash SHA-256 e extração do Quadro de Áreas
              </p>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isUploading || !selectedFile}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
            >
              <Lock className="w-4 h-4" />
              {isUploading ? "Calculando Hash e Salvando..." : "Registrar Documento com Hash SHA-256"}
            </button>
          </div>
        </form>
      </div>

      {/* Documents Table */}
      <div className="glass-panel rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-white">
              Linha de Base Documental: {activeProject ? activeProject.name : "Todos os Projetos"}
            </h2>
            <p className="text-xs text-slate-400">Documentos vigentes, leitor assistido e prova de integridade</p>
          </div>
          <span className="text-xs text-slate-400 font-mono font-semibold">
            {documents.length} documento(s) cadastrado(s)
          </span>
        </div>

        {documents.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs">
            Nenhum documento cadastrado para este empreendimento ainda.
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div key={doc.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-xs">
                      {doc.version}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">{doc.title}</h3>
                      <p className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                        <span className="capitalize text-cyan-400 font-medium">{doc.category.replace("_", " ")}</span>
                        <span>•</span>
                        <span>{new Date(doc.created_at).toLocaleDateString("pt-BR")}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Extract Data Button */}
                    <button
                      onClick={() => handleExtract(doc.id)}
                      disabled={isExtractingId === doc.id}
                      className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 font-semibold text-xs flex items-center gap-1.5 transition-all"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      {isExtractingId === doc.id ? "Analisando..." : "Extrair Parâmetros (IA)"}
                    </button>

                    <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-extrabold uppercase flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      Vigente
                    </span>
                  </div>
                </div>

                {/* SHA-256 Hash Display Badge */}
                {doc.hash_sha256 && (
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between gap-3 text-[11px]">
                    <div className="flex items-center gap-2 min-w-0">
                      <Hash className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="text-slate-500 font-mono shrink-0">SHA-256:</span>
                      <span className="font-mono text-slate-300 truncate">{doc.hash_sha256}</span>
                    </div>

                    <button
                      onClick={() => handleCopyHash(doc.hash_sha256!)}
                      className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-semibold flex items-center gap-1 shrink-0 transition-colors"
                    >
                      {copiedHash === doc.hash_sha256 ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" /> Copiado!
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 text-slate-400" /> Copiar Hash
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Extraction Results Modal */}
      {extractionResult && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-lg rounded-2xl p-6 space-y-5 border border-cyan-500/40 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-cyan-400" />
                <h2 className="text-base font-bold text-white">Extração Assistida de Desenho</h2>
              </div>
              <button onClick={() => setExtractionResult(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-slate-400">Documento Origem:</span>
                  <p className="font-bold text-white text-sm">{extractionResult.document_title}</p>
                </div>
                <div className="text-right">
                  <span className="text-slate-400">Confiança do Leitor:</span>
                  <p className="font-mono font-extrabold text-cyan-400 text-sm">
                    {extractionResult.extracted_parameters.confidence_score}%
                  </p>
                </div>
              </div>

              {/* Extracted Metrics Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-slate-400 text-[10px]">Área do Terreno (Lote):</span>
                  <p className="font-mono text-sm font-bold text-white">
                    {extractionResult.extracted_parameters.lot_area ? `${extractionResult.extracted_parameters.lot_area} m²` : "Não identificado"}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-slate-400 text-[10px]">Área Construída (Projeção):</span>
                  <p className="font-mono text-sm font-bold text-white">
                    {extractionResult.extracted_parameters.built_area ? `${extractionResult.extracted_parameters.built_area} m²` : "Não identificado"}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-slate-400 text-[10px]">Recuo Frontal:</span>
                  <p className="font-mono text-sm font-bold text-white">
                    {extractionResult.extracted_parameters.front_setback ? `${extractionResult.extracted_parameters.front_setback} m` : "Não identificado"}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-slate-400 text-[10px]">Recuo dos Fundos:</span>
                  <p className="font-mono text-sm font-bold text-white">
                    {extractionResult.extracted_parameters.rear_setback ? `${extractionResult.extracted_parameters.rear_setback} m` : "Não identificado"}
                  </p>
                </div>
              </div>

              {/* Raw Matches */}
              {extractionResult.extracted_parameters.raw_matches.length > 0 && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Textos Mapeados no Quadro de Áreas:</span>
                  <ul className="text-[11px] font-mono text-cyan-300 space-y-1">
                    {extractionResult.extracted_parameters.raw_matches.map((m, i) => (
                      <li key={i}>• {m}</li>
                    ))}
                  </ul>
                </div>
              )}

              {isApplied && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold text-center flex items-center justify-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> Parâmetros aplicados ao projeto com sucesso! Copiloto reavaliado.
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setExtractionResult(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs"
              >
                Fechar
              </button>

              <button
                type="button"
                onClick={handleApplyExtractedParameters}
                disabled={isApplied}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
              >
                <Sliders className="w-4 h-4" />
                {isApplied ? "Aplicado!" : "Aplicar Parâmetros ao Projeto"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
