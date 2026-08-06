"use client";

import { useState, useEffect } from "react";
import { Building2, Plus, MapPin, CheckCircle2, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { fetchProjects, createProject, Project } from "@/lib/api";

const MOCK_PROJECTS: Project[] = [
  {
    id: "acacias",
    organization_id: "org-1",
    name: "Residencial das Acácias",
    description: "Residencial Unifamiliar em Lajeado - RS",
    city_ibge: "BR-RS-4311403",
    city_name: "Lajeado",
    state: "RS",
    zone: "Z2",
    building_type: "residencial_unifamiliar",
    built_area: 240,
    lot_area: 450,
    floors: 2,
    front_setback: 4.5,
    side_setback: 1.8,
    rear_setback: 3.0,
    occupancy_rate: 53.3,
    permeability_rate: 22.5,
    parking_spaces: 2,
    status: "Pré-Análise Concluída",
    is_official_baseline: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    validations: []
  },
  {
    id: "sol_nascente",
    organization_id: "org-1",
    name: "Residencial Sol Nascente",
    description: "Inconsistência de Recuo Frontal",
    city_ibge: "BR-RS-4311403",
    city_name: "Lajeado",
    state: "RS",
    zone: "Z2",
    building_type: "residencial_unifamiliar",
    built_area: 220,
    lot_area: 360,
    floors: 2,
    front_setback: 3.2,
    side_setback: 1.2,
    rear_setback: 2.5,
    occupancy_rate: 61.1,
    permeability_rate: 12.0,
    parking_spaces: 1,
    status: "Ajuste de Recuo Pendente",
    is_official_baseline: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    validations: []
  }
];

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>(MOCK_PROJECTS);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [zone, setZone] = useState("Z2");
  const [lotArea, setLotArea] = useState(400);
  const [builtArea, setBuiltArea] = useState(200);
  const [frontSetback, setFrontSetback] = useState(4.5);

  useEffect(() => {
    async function loadData() {
      const data = await fetchProjects();
      if (data && data.length > 0) {
        setProjects(data);
      }
    }
    loadData();
  }, []);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;

    setIsSubmitting(true);
    const orgId = projects[0]?.organization_id || "org-1";

    const newProject = await createProject({
      organization_id: orgId,
      name,
      city_ibge: "BR-RS-4311403",
      city_name: "Lajeado",
      zone,
      building_type: "residencial_unifamiliar",
      lot_area: Number(lotArea),
      built_area: Number(builtArea),
      floors: 2,
      front_setback: Number(frontSetback),
      side_setback: 1.5,
      rear_setback: 2.5,
      occupancy_rate: (Number(builtArea) / Number(lotArea)) * 100
    });

    if (newProject) {
      setProjects(prev => [newProject, ...prev]);
    } else {
      // Local fallback creation
      const fallback: Project = {
        id: `proj-${Date.now()}`,
        organization_id: orgId,
        name,
        city_ibge: "BR-RS-4311403",
        city_name: "Lajeado",
        state: "RS",
        zone,
        building_type: "residencial_unifamiliar",
        lot_area: Number(lotArea),
        built_area: Number(builtArea),
        floors: 2,
        front_setback: Number(frontSetback),
        side_setback: 1.5,
        rear_setback: 2.5,
        occupancy_rate: (Number(builtArea) / Number(lotArea)) * 100,
        permeability_rate: 20.0,
        parking_spaces: 1,
        status: "estudo_preliminar",
        is_official_baseline: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        validations: []
      };
      setProjects(prev => [fallback, ...prev]);
    }

    setIsSubmitting(false);
    setIsModalOpen(false);
    setName("");
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Módulo 2 • Cadastro e Gestão</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Empreendimentos & Linhas de Base</h1>
          <p className="text-xs text-slate-400 mt-1">
            Gestão unificada de obras, tipologias e consolidação do projeto oficial aprovado.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> Novo Empreendimento
        </button>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {projects.map((p) => (
          <div key={p.id} className="glass-panel rounded-2xl p-6 space-y-4 hover:border-cyan-500/40 transition-all">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">{p.zone} • {p.city_name}</span>
                <h2 className="text-lg font-bold text-white mt-0.5">{p.name}</h2>
                <p className="text-xs text-slate-400 flex items-center gap-1 mt-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-500" /> {p.city_name} / {p.state}
                </p>
              </div>

              {p.is_official_baseline ? (
                <span className="px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-bold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Linha de Base Oficial
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-400 text-xs font-medium">
                  Estudo Preliminar
                </span>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
              <div>
                <span className="text-slate-500 text-[10px] block uppercase">Área Construída</span>
                <span className="font-bold text-slate-200">{p.built_area} m²</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block uppercase">Área do Lote</span>
                <span className="font-bold text-slate-200">{p.lot_area} m²</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block uppercase">Recuo Frontal</span>
                <span className="font-bold text-cyan-400">{p.front_setback} m</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
              <span className="text-slate-400">
                Taxa Ocupação: <strong className="text-slate-200">{((p.built_area / p.lot_area) * 100).toFixed(1)}%</strong>
              </span>

              <Link
                href="/approvals"
                className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition-colors flex items-center gap-1"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                Copiloto de Aprovação
              </Link>
            </div>
          </div>
        ))}
      </div>

      {/* Create Project Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-lg rounded-2xl p-6 space-y-4 border border-cyan-500/30">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white">Cadastrar Novo Empreendimento</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">Nome do Empreendimento:</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Residencial Villa Real"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Zoneamento Municipal:</label>
                  <select
                    value={zone}
                    onChange={e => setZone(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  >
                    <option value="Z2">Zona Z2 (Lajeado)</option>
                    <option value="Z1">Zona Z1 (Lajeado)</option>
                    <option value="Z3">Zona Z3 (Lajeado)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Recuo Frontal (m):</label>
                  <input
                    type="number"
                    step="0.1"
                    value={frontSetback}
                    onChange={e => setFrontSetback(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Área do Lote (m²):</label>
                  <input
                    type="number"
                    value={lotArea}
                    onChange={e => setLotArea(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Área Construída (m²):</label>
                  <input
                    type="number"
                    value={builtArea}
                    onChange={e => setBuiltArea(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-200"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold shadow-md shadow-cyan-500/20"
                >
                  {isSubmitting ? "Cadastrando..." : "Cadastrar e Avaliar Regras"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
