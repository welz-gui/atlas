"use client";

import { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  HelpCircle, 
  FileText, 
  RotateCcw,
  Sliders,
  Download,
  Wifi,
  WifiOff,
  FileCheck
} from "lucide-react";
import { 
  fetchProjects, 
  updateProjectParameters, 
  getProjectReportPDFUrl,
  Project, 
  ValidationRecord 
} from "@/lib/api";

const MOCK_PROJECTS: Project[] = [
  {
    id: "sol_nascente",
    organization_id: "org-1",
    name: "Residencial Sol Nascente (Com Inconsistência)",
    description: "Projeto de teste",
    city_ibge: "BR-RS-4311403",
    city_name: "Lajeado",
    state: "RS",
    zone: "Z2",
    building_type: "residencial_unifamiliar",
    lot_area: 360,
    built_area: 220,
    floors: 2,
    front_setback: 3.20,
    side_setback: 1.20,
    rear_setback: 2.50,
    occupancy_rate: 61.1,
    permeability_rate: 12.0,
    parking_spaces: 1,
    status: "estudo_preliminar",
    is_official_baseline: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    validations: [
      {
        id: "val-1",
        rule_id: "lajeado_recuo_frontal_z2",
        rule_title: "Recuo Frontal Mínimo - Zona Z2",
        field: "front_setback",
        status: "nao_conforme",
        expected_value: ">= 4.0m",
        actual_value: "3.20m",
        details: "Violação de 0.80m. O recuo informado é inferior ao mínimo obrigatório.",
        source_citation: "Plano Diretor de Lajeado, Art. 45 (Zona Z2)",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-2",
        rule_id: "lajeado_taxa_ocupacao_max_z2",
        rule_title: "Taxa de Ocupação Máxima - Zona Z2",
        field: "occupancy_rate",
        status: "nao_conforme",
        expected_value: "<= 60.0%",
        actual_value: "61.1%",
        details: "Supera o limite máximo em 1.1%. Reduza a área do pavimento térreo.",
        source_citation: "Plano Diretor de Lajeado, Tabela Z2",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-3",
        rule_id: "lajeado_recuo_fundos_z2",
        rule_title: "Recuo dos Fundos Mínimo - Zona Z2",
        field: "rear_setback",
        status: "nao_conforme",
        expected_value: ">= 3.00m",
        actual_value: "2.50m",
        details: "O recuo dos fundos informado é inferior ao mínimo de 3.00m exigido.",
        source_citation: "Plano Diretor de Lajeado, Art. 46 (Zona Z2)",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-4",
        rule_id: "lajeado_taxa_permeabilidade_min_z2",
        rule_title: "Taxa de Permeabilidade Mínima - Zona Z2",
        field: "permeability_rate",
        status: "nao_conforme",
        expected_value: ">= 15.0%",
        actual_value: "12.0%",
        details: "Área verde/infiltrável inferior ao mínimo obrigatório de 15.0%.",
        source_citation: "Código de Edificações de Lajeado, Art. 38",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-5",
        rule_id: "lajeado_gabarito_maximo_z2",
        rule_title: "Gabarito Máximo de Pavimentos",
        field: "floors",
        status: "conforme",
        expected_value: "<= 3 pavimentos",
        actual_value: "2 pavimentos",
        details: "Dentro do limite para residência unifamiliar na Zona Z2.",
        source_citation: "Plano Diretor de Lajeado, Art. 52",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-6",
        rule_id: "lajeado_acessibilidade_nbr9050",
        rule_title: "Conformidade NBR 9050 (Acessibilidade)",
        field: "accessibility_check",
        status: "nao_verificavel",
        expected_value: "Laudo Acessibilidade",
        actual_value: "Pendente",
        details: "Necessita upload de arquivo na aba Documentos para análise gráfica.",
        source_citation: "NBR 9050 / Lei de Acessibilidade",
        validated_at: new Date().toISOString()
      }
    ]
  },
  {
    id: "acacias",
    organization_id: "org-1",
    name: "Residencial das Acácias (100% Conforme)",
    description: "Projeto aprovado",
    city_ibge: "BR-RS-4311403",
    city_name: "Lajeado",
    state: "RS",
    zone: "Z2",
    building_type: "residencial_unifamiliar",
    lot_area: 450,
    built_area: 240,
    floors: 2,
    front_setback: 4.50,
    side_setback: 1.80,
    rear_setback: 3.50,
    occupancy_rate: 53.3,
    permeability_rate: 22.5,
    parking_spaces: 2,
    status: "pre_analise",
    is_official_baseline: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    validations: [
      {
        id: "val-11",
        rule_id: "lajeado_recuo_frontal_z2",
        rule_title: "Recuo Frontal Mínimo - Zona Z2",
        field: "front_setback",
        status: "conforme",
        expected_value: ">= 4.0m",
        actual_value: "4.50m",
        details: "Parâmetro dentro do limite exigido pela norma municipal vigente.",
        source_citation: "Plano Diretor de Lajeado, Art. 45 (Zona Z2)",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-12",
        rule_id: "lajeado_taxa_ocupacao_max_z2",
        rule_title: "Taxa de Ocupação Máxima - Zona Z2",
        field: "occupancy_rate",
        status: "conforme",
        expected_value: "<= 60.0%",
        actual_value: "53.3%",
        details: "Parâmetro dentro do limite exigido pela norma municipal vigente.",
        source_citation: "Plano Diretor de Lajeado, Tabela Z2",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-13",
        rule_id: "lajeado_recuo_fundos_z2",
        rule_title: "Recuo dos Fundos Mínimo - Zona Z2",
        field: "rear_setback",
        status: "conforme",
        expected_value: ">= 3.00m",
        actual_value: "3.50m",
        details: "Parâmetro dentro do limite exigido pela norma municipal vigente.",
        source_citation: "Plano Diretor de Lajeado, Art. 46 (Zona Z2)",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-14",
        rule_id: "lajeado_taxa_permeabilidade_min_z2",
        rule_title: "Taxa de Permeabilidade Mínima - Zona Z2",
        field: "permeability_rate",
        status: "conforme",
        expected_value: ">= 15.0%",
        actual_value: "22.5%",
        details: "Parâmetro dentro do limite exigido pela norma municipal vigente.",
        source_citation: "Código de Edificações de Lajeado, Art. 38",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-15",
        rule_id: "lajeado_gabarito_maximo_z2",
        rule_title: "Gabarito Máximo de Pavimentos",
        field: "floors",
        status: "conforme",
        expected_value: "<= 3 pavimentos",
        actual_value: "2 pavimentos",
        details: "Parâmetro dentro do limite exigido pela norma municipal vigente.",
        source_citation: "Plano Diretor de Lajeado, Art. 52",
        validated_at: new Date().toISOString()
      },
      {
        id: "val-16",
        rule_id: "lajeado_acessibilidade_nbr9050",
        rule_title: "Conformidade NBR 9050 (Acessibilidade)",
        field: "accessibility_check",
        status: "nao_verificavel",
        expected_value: "Laudo Acessibilidade",
        actual_value: "Pendente",
        details: "Necessita upload de arquivo na aba Documentos para análise gráfica.",
        source_citation: "NBR 9050 / Lei de Acessibilidade",
        validated_at: new Date().toISOString()
      }
    ]
  }
];

export default function ApprovalsPage() {
  const [projects, setProjects] = useState<Project[]>(MOCK_PROJECTS);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("sol_nascente");
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);

  useEffect(() => {
    async function loadBackendData() {
      const data = await fetchProjects();
      if (data && data.length > 0) {
        setProjects(data);
        setSelectedProjectId(data[0].id);
        setIsLiveConnected(true);
      } else {
        setIsLiveConnected(false);
      }
    }
    loadBackendData();
  }, []);

  const activeProject = projects.find(p => p.id === selectedProjectId) || projects[0];

  // Parameters for real-time simulator
  const [frontSetback, setFrontSetback] = useState<number>(activeProject.front_setback);
  const [builtArea, setBuiltArea] = useState<number>(activeProject.built_area);
  const [rearSetback, setRearSetback] = useState<number>(activeProject.rear_setback || 3.0);
  const [permeabilityRate, setPermeabilityRate] = useState<number>(activeProject.permeability_rate || 20.0);

  useEffect(() => {
    if (activeProject) {
      setFrontSetback(activeProject.front_setback);
      setBuiltArea(activeProject.built_area);
      setRearSetback(activeProject.rear_setback || 3.0);
      setPermeabilityRate(activeProject.permeability_rate || 20.0);
    }
  }, [selectedProjectId]);

  const handleUpdateParameter = async (
    newFrontSetback: number,
    newBuiltArea: number,
    newRearSetback: number,
    newPermeability: number
  ) => {
    setFrontSetback(newFrontSetback);
    setBuiltArea(newBuiltArea);
    setRearSetback(newRearSetback);
    setPermeabilityRate(newPermeability);

    if (isLiveConnected && activeProject) {
      setIsUpdating(true);
      const updated = await updateProjectParameters(activeProject.id, {
        front_setback: newFrontSetback,
        built_area: newBuiltArea,
        rear_setback: newRearSetback,
        permeability_rate: newPermeability
      });
      if (updated) {
        setProjects(prev => prev.map(p => p.id === updated.id ? updated : p));
      }
      setIsUpdating(false);
    } else {
      const lotArea = activeProject.lot_area || 360;
      const occRate = (newBuiltArea / lotArea) * 100;
      const isSetbackOk = newFrontSetback >= 4.0;
      const isOccOk = occRate <= 60.0;
      const isRearOk = newRearSetback >= 3.0;
      const isPermOk = newPermeability >= 15.0;

      const updatedValidations: ValidationRecord[] = (activeProject.validations || []).map(v => {
        if (v.rule_id === "lajeado_recuo_frontal_z2") {
          return {
            ...v,
            status: isSetbackOk ? "conforme" : "nao_conforme",
            actual_value: `${newFrontSetback.toFixed(2)}m`,
            details: isSetbackOk ? "Parâmetro dentro do limite da norma municipal." : `Violação de ${(4.0 - newFrontSetback).toFixed(2)}m.`
          };
        }
        if (v.rule_id === "lajeado_taxa_ocupacao_max_z2") {
          return {
            ...v,
            status: isOccOk ? "conforme" : "nao_conforme",
            actual_value: `${occRate.toFixed(1)}%`,
            details: isOccOk ? "Área construída dentro do limite exigido." : `Supera a taxa máxima em ${(occRate - 60.0).toFixed(1)}%.`
          };
        }
        if (v.rule_id === "lajeado_recuo_fundos_z2") {
          return {
            ...v,
            status: isRearOk ? "conforme" : "nao_conforme",
            actual_value: `${newRearSetback.toFixed(2)}m`,
            details: isRearOk ? "Recuo dos fundos em conformidade." : `Inferior ao mínimo obrigatório de 3.00m.`
          };
        }
        if (v.rule_id === "lajeado_taxa_permeabilidade_min_z2") {
          return {
            ...v,
            status: isPermOk ? "conforme" : "nao_conforme",
            actual_value: `${newPermeability.toFixed(1)}%`,
            details: isPermOk ? "Área permeável suficiente no lote." : `Inferior ao mínimo exigido de 15.0%.`
          };
        }
        return v;
      });

      setProjects(prev => prev.map(p => p.id === activeProject.id ? {
        ...p,
        front_setback: newFrontSetback,
        built_area: newBuiltArea,
        rear_setback: newRearSetback,
        permeability_rate: newPermeability,
        occupancy_rate: occRate,
        validations: updatedValidations
      } : p));
    }
  };

  const handleExportPDF = () => {
    if (activeProject) {
      const pdfUrl = getProjectReportPDFUrl(activeProject.id);
      window.open(pdfUrl, "_blank");
    }
  };

  const validations = activeProject.validations || [];
  const conformeCount = validations.filter(r => r.status === "conforme").length;
  const naoConformeCount = validations.filter(r => r.status === "nao_conforme").length;
  const naoVerificavelCount = validations.filter(r => r.status === "nao_verificavel").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Estágio 1 • Pré-Análise Legal</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Copiloto de Aprovação Municipal</h1>
          <p className="text-xs text-slate-400 mt-1">
            Verificação autônoma de parâmetros urbanísticos para Lajeado / RS.
          </p>
        </div>

        {/* Backend Status & Project Selector */}
        <div className="flex items-center gap-3">
          <div className={`px-2.5 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1.5 border ${
            isLiveConnected 
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" 
              : "bg-slate-800 text-slate-400 border-slate-700"
          }`}>
            {isLiveConnected ? <Wifi className="w-3 h-3 text-emerald-400 animate-pulse" /> : <WifiOff className="w-3 h-3 text-slate-400" />}
            <span>{isLiveConnected ? "FastAPI Conectado" : "Modo Simulação Local"}</span>
          </div>

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
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-emerald-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase">Regras Conformes</p>
            <p className="text-2xl font-extrabold text-white mt-1">{conformeCount}</p>
          </div>
          <CheckCircle2 className="w-8 h-8 text-emerald-400/80" />
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-amber-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase">Não Conformes / Bloqueios</p>
            <p className="text-2xl font-extrabold text-amber-400 mt-1">{naoConformeCount}</p>
          </div>
          <XCircle className="w-8 h-8 text-amber-400/80" />
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-slate-500 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase">Não Verificáveis (Pendente ARQ)</p>
            <p className="text-2xl font-extrabold text-slate-300 mt-1">{naoVerificavelCount}</p>
          </div>
          <HelpCircle className="w-8 h-8 text-slate-500" />
        </div>
      </div>

      {/* Real-Time Parameter Simulator Card */}
      <div className="glass-panel rounded-2xl p-6 border-cyan-500/30 space-y-4 glow-blue">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white">
              Simulador em Tempo Real: {activeProject.name}
            </h2>
            {isUpdating && <span className="text-[10px] text-cyan-400 animate-pulse font-semibold">Atualizando API FastAPI...</span>}
          </div>
          <button
            onClick={() => handleUpdateParameter(4.0, 200, 3.5, 20.0)}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
          >
            <RotateCcw className="w-3 h-3" /> Aplicar Valores Recomendados
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-2">
          <div>
            <div className="flex justify-between text-[11px] mb-2">
              <span className="text-slate-300 font-semibold">Recuo Frontal (m):</span>
              <span className={`font-mono font-bold ${frontSetback >= 4.0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {frontSetback.toFixed(2)}m (Min: 4.0m)
              </span>
            </div>
            <input
              type="range"
              min="2.0"
              max="6.0"
              step="0.1"
              value={frontSetback}
              onChange={(e) => handleUpdateParameter(parseFloat(e.target.value), builtArea, rearSetback, permeabilityRate)}
              className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-[11px] mb-2">
              <span className="text-slate-300 font-semibold">Recuo Fundos (m):</span>
              <span className={`font-mono font-bold ${rearSetback >= 3.0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {rearSetback.toFixed(2)}m (Min: 3.0m)
              </span>
            </div>
            <input
              type="range"
              min="1.5"
              max="5.0"
              step="0.1"
              value={rearSetback}
              onChange={(e) => handleUpdateParameter(frontSetback, builtArea, parseFloat(e.target.value), permeabilityRate)}
              className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-[11px] mb-2">
              <span className="text-slate-300 font-semibold">Área Construída (m²):</span>
              <span className={`font-mono font-bold ${((builtArea / (activeProject.lot_area || 360)) * 100) <= 60.0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {builtArea}m² ({((builtArea / (activeProject.lot_area || 360)) * 100).toFixed(1)}% Max: 60%)
              </span>
            </div>
            <input
              type="range"
              min="150"
              max="260"
              step="5"
              value={builtArea}
              onChange={(e) => handleUpdateParameter(frontSetback, parseFloat(e.target.value), rearSetback, permeabilityRate)}
              className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-[11px] mb-2">
              <span className="text-slate-300 font-semibold">Permeabilidade (%):</span>
              <span className={`font-mono font-bold ${permeabilityRate >= 15.0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {permeabilityRate.toFixed(1)}% (Min: 15%)
              </span>
            </div>
            <input
              type="range"
              min="5.0"
              max="35.0"
              step="1"
              value={permeabilityRate}
              onChange={(e) => handleUpdateParameter(frontSetback, builtArea, rearSetback, parseFloat(e.target.value))}
              className="w-full accent-cyan-400 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* Rules Evaluation List */}
      <div className="glass-panel rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-white">Relatório de Verificação Normativa</h2>
            <p className="text-xs text-slate-400">Jurisdição: {activeProject.city_ibge} ({activeProject.city_name} / {activeProject.state}) • Zona {activeProject.zone}</p>
          </div>

          <button
            onClick={handleExportPDF}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
          >
            <FileCheck className="w-4 h-4" /> Emitir Laudo PDF (SHA-256)
          </button>
        </div>

        <div className="space-y-4">
          {validations.map((rule) => (
            <div
              key={rule.id || rule.rule_id}
              className={`p-5 rounded-xl border transition-all ${
                rule.status === "conforme"
                  ? "bg-slate-900/60 border-emerald-500/30"
                  : rule.status === "nao_conforme"
                  ? "bg-amber-950/20 border-amber-500/40"
                  : "bg-slate-900/40 border-slate-800"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
                <div className="flex items-center gap-3">
                  {rule.status === "conforme" && (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  )}
                  {rule.status === "nao_conforme" && (
                    <XCircle className="w-5 h-5 text-amber-400 shrink-0" />
                  )}
                  {rule.status === "nao_verificavel" && (
                    <HelpCircle className="w-5 h-5 text-slate-400 shrink-0" />
                  )}
                  <h3 className="text-sm font-bold text-white">{rule.rule_title}</h3>
                </div>

                <span
                  className={`px-3 py-1 rounded-full text-[11px] font-extrabold tracking-wide uppercase self-start sm:self-auto ${
                    rule.status === "conforme"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : rule.status === "nao_conforme"
                      ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                      : "bg-slate-800 text-slate-400 border border-slate-700"
                  }`}
                >
                  {rule.status === "conforme" && "Conforme"}
                  {rule.status === "nao_conforme" && "Não Conforme (Bloqueio)"}
                  {rule.status === "nao_verificavel" && "Não Verificável"}
                </span>
              </div>

              <p className="text-xs text-slate-300 ml-8 mb-3">{rule.details}</p>

              <div className="ml-8 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-slate-500 text-[11px] block">Exigido por Norma:</span>
                  <span className="font-mono text-slate-200 font-semibold">{rule.expected_value}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px] block">Valor Informado / Calculado:</span>
                  <span className="font-mono text-cyan-400 font-bold">{rule.actual_value}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[11px] block">Fonte da Regra:</span>
                  <span className="text-slate-400 italic text-[11px] flex items-center gap-1">
                    <FileText className="w-3 h-3 text-cyan-400 shrink-0" />
                    {rule.source_citation}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
