"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Building2,
  CheckCircle2,
  HelpCircle,
  Landmark,
  Plus,
  X,
  XCircle,
} from "lucide-react";
import { ApiError, createProject, formatParam, humanize } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

const NUMERIC_FIELDS = [
  { key: "lot_area", label: "Área do lote (m²)" },
  { key: "built_area", label: "Área construída (m²)" },
  { key: "floors", label: "Pavimentos" },
  { key: "front_setback", label: "Recuo frontal (m)" },
  { key: "side_setback", label: "Recuo lateral (m)" },
  { key: "rear_setback", label: "Recuo dos fundos (m)" },
  { key: "permeability_rate", label: "Permeabilidade (%)" },
  { key: "parking_spaces", label: "Vagas" },
];

const IDENTITY_FIELDS = [
  { key: "address", label: "Logradouro" },
  { key: "address_number", label: "Número" },
  { key: "district", label: "Bairro" },
  { key: "postal_code", label: "CEP" },
  { key: "lot", label: "Lote" },
  { key: "block", label: "Quadra" },
  { key: "registry_number", label: "Matrícula" },
  { key: "municipal_registration", label: "Inscrição municipal" },
  { key: "owner_name", label: "Proprietário" },
  { key: "technical_responsible_name", label: "Responsável técnico" },
  { key: "technical_responsible_registry", label: "CREA / CAU" },
];

const MUNICIPALITIES = [
  { city_ibge: "BR-RS-4311403", city_name: "Lajeado", state: "RS" },
  { city_ibge: "BR-RS-4301008", city_name: "Arroio do Meio", state: "RS" },
];

export default function ProjectsPage() {
  const { can } = useAuth();
  const { projects, isLoading, error, reload } = useProjects();
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
              Cadastro
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Empreendimentos</h1>
          <p className="text-xs text-slate-400 mt-1">
            Parâmetros não informados aparecem como tal e produzem verificação
            &quot;não verificável&quot; — nunca são preenchidos com zero.
          </p>
        </div>

        {can("project:write") && (
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Novo empreendimento
          </button>
        )}
      </div>

      {error && <ErrorBanner error={error} onRetry={reload} />}
      {isLoading && <LoadingState label="Carregando empreendimentos..." />}

      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          title="Nenhum empreendimento cadastrado"
          description="Cadastre o primeiro empreendimento para iniciar a pré-análise urbanística."
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {projects.map((project) => {
          const validations = project.validations ?? [];
          const version = project.current_version;
          const conforme = validations.filter((v) => v.status === "conforme").length;
          const naoConforme = validations.filter((v) => v.status === "nao_conforme").length;
          const naoVerificavel = validations.filter(
            (v) => v.status === "nao_verificavel"
          ).length;

          return (
            <div key={project.id} className="glass-panel rounded-2xl p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-bold text-white truncate">
                    {project.name}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {project.city_name}/{project.state}
                    {version && ` • Zona ${version.zone}`}
                    {project.lot && ` • lote ${project.lot}`}
                    {project.block && `, quadra ${project.block}`}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Licenciamento: {humanize(project.licensing_status)}
                  </p>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  {version && (
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-slate-800 text-slate-300 border border-slate-700">
                      v{version.version_number} · {humanize(version.state)}
                    </span>
                  )}
                  {project.official_baseline && (
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                      <Landmark className="w-3 h-3" /> base v
                      {project.official_baseline.version_number}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <Param label="Área do lote" value={formatParam(version?.lot_area, "m²", 0)} />
                <Param
                  label="Área construída"
                  value={formatParam(version?.built_area, "m²", 0)}
                />
                <Param
                  label="Ocupação"
                  value={formatParam(version?.occupancy_rate, "%", 1)}
                  hint="derivada"
                />
                <Param label="Recuo frontal" value={formatParam(version?.front_setback, "m")} />
                <Param label="Recuo fundos" value={formatParam(version?.rear_setback, "m")} />
                <Param
                  label="Permeabilidade"
                  value={formatParam(version?.permeability_rate, "%", 1)}
                />
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {conforme}
                  </span>
                  <span className="flex items-center gap-1.5 text-red-400 font-semibold">
                    <XCircle className="w-3.5 h-3.5" /> {naoConforme}
                  </span>
                  <span className="flex items-center gap-1.5 text-blue-300 font-semibold">
                    <HelpCircle className="w-3.5 h-3.5" /> {naoVerificavel}
                  </span>
                </div>

                <Link
                  href="/approvals"
                  className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                >
                  Abrir no copiloto <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {isModalOpen && (
        <NewProjectModal
          onClose={() => setIsModalOpen(false)}
          onCreated={() => {
            setIsModalOpen(false);
            reload();
          }}
        />
      )}
    </div>
  );
}

function Param({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  const notInformed = value === "não informado";
  return (
    <div>
      <span className="text-slate-500 text-[11px] block">
        {label}
        {hint && <span className="text-slate-600"> ({hint})</span>}:
      </span>
      <span
        className={`font-mono font-semibold ${
          notInformed ? "text-blue-300/70 italic" : "text-slate-200"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

/** Campos numéricos ficam vazios por padrão — vazio significa não informado. */
function NewProjectModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [zone, setZone] = useState("Z2");
  const [municipalityCode, setMunicipalityCode] = useState("BR-RS-4311403");
  const [values, setValues] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name) return;

    setIsSaving(true);
    setError(null);
    try {
      const numeric = Object.fromEntries(
        NUMERIC_FIELDS.map(({ key }) => {
          const raw = values[key];
          // String vazia vira null: o campo não foi informado.
          return [key, raw === undefined || raw.trim() === "" ? null : Number(raw)];
        })
      );
      const identity = Object.fromEntries(
        IDENTITY_FIELDS.map(({ key }) => [key, values[key]?.trim() || undefined])
      );
      const municipality = MUNICIPALITIES.find(
        (item) => item.city_ibge === municipalityCode
      )!;
      await createProject({ name, zone, ...municipality, ...identity, ...numeric });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  const field = (key: string, label: string, type = "text") => (
    <label key={key} className="block">
      <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">{label}</span>
      <input
        type={type}
        step={type === "number" ? "any" : undefined}
        placeholder={type === "number" ? "não informado" : undefined}
        value={values[key] ?? ""}
        onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none placeholder:text-slate-600 placeholder:text-[11px]"
      />
    </label>
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
      <div className="glass-panel rounded-2xl p-6 w-full max-w-3xl space-y-5 my-8">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white">Novo empreendimento</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <label className="block sm:col-span-2">
              <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
                Nome do empreendimento <span className="text-cyan-400">*</span>
              </span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
                Zona
              </span>
              <input
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </label>
          </div>

          <label className="block max-w-md">
            <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
              Município do empreendimento
            </span>
            <select
              value={municipalityCode}
              onChange={(event) => setMunicipalityCode(event.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
            >
              {MUNICIPALITIES.map((municipality) => (
                <option key={municipality.city_ibge} value={municipality.city_ibge}>
                  {municipality.city_name}/{municipality.state}
                </option>
              ))}
            </select>
            <span className="text-[10px] text-slate-500 mt-1 block">
              Define quais normas municipais serão aplicadas ao projeto.
            </span>
          </label>

          <div>
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wide mb-3">
              Localização e partes
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {IDENTITY_FIELDS.map(({ key, label }) => field(key, label))}
            </div>
          </div>

          <div>
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wide mb-1">
              Parâmetros urbanísticos (versão 1)
            </h3>
            <p className="text-[11px] text-blue-300 mb-3">
              Deixe em branco o que ainda não souber. Campo vazio é registrado como
              &quot;não informado&quot; e gera verificação não verificável — o Atlas não
              assume zero.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {NUMERIC_FIELDS.map(({ key, label }) => field(key, label, "number"))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-800/60"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold disabled:opacity-50"
            >
              {isSaving ? "Salvando..." : "Cadastrar e analisar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
