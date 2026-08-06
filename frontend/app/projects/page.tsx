"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Building2,
  CheckCircle2,
  HelpCircle,
  Plus,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import {
  ApiError,
  Organization,
  createProject,
  fetchOrganizations,
  formatParam,
} from "@/lib/api";
import { useProjects } from "@/lib/useProjects";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/StateViews";

export default function ProjectsPage() {
  const { projects, isLoading, error, reload } = useProjects();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    fetchOrganizations()
      .then(setOrganizations)
      .catch(() => setOrganizations([]));
  }, []);

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

        <button
          onClick={() => setIsModalOpen(true)}
          disabled={organizations.length === 0}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> Novo empreendimento
        </button>
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
          const conforme = validations.filter((v) => v.status === "conforme").length;
          const naoConforme = validations.filter((v) => v.status === "nao_conforme").length;
          const naoVerificavel = validations.filter(
            (v) => v.status === "nao_verificavel"
          ).length;

          return (
            <div key={project.id} className="glass-panel rounded-2xl p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-white">{project.name}</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {project.city_name}/{project.state} • Zona {project.zone} •{" "}
                    {project.building_type.replace(/_/g, " ")}
                  </p>
                </div>
                {project.is_official_baseline && (
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shrink-0">
                    Linha de base
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <Param label="Área do lote" value={formatParam(project.lot_area, "m²")} />
                <Param label="Área construída" value={formatParam(project.built_area, "m²")} />
                <Param
                  label="Taxa de ocupação"
                  value={formatParam(project.occupancy_rate, "%", 1)}
                  hint="derivada"
                />
                <Param label="Recuo frontal" value={formatParam(project.front_setback, "m")} />
                <Param label="Recuo fundos" value={formatParam(project.rear_setback, "m")} />
                <Param
                  label="Permeabilidade"
                  value={formatParam(project.permeability_rate, "%", 1)}
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
          organizations={organizations}
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
  organizations,
  onClose,
  onCreated,
}: {
  organizations: Organization[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [organizationId, setOrganizationId] = useState(organizations[0]?.id ?? "");
  const [zone, setZone] = useState("Z2");
  const [values, setValues] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const numericFields = [
    { key: "lot_area", label: "Área do lote (m²)" },
    { key: "built_area", label: "Área construída (m²)" },
    { key: "floors", label: "Pavimentos" },
    { key: "front_setback", label: "Recuo frontal (m)" },
    { key: "side_setback", label: "Recuo lateral (m)" },
    { key: "rear_setback", label: "Recuo dos fundos (m)" },
    { key: "permeability_rate", label: "Permeabilidade (%)" },
    { key: "parking_spaces", label: "Vagas" },
  ];

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name || !organizationId) return;

    setIsSaving(true);
    setError(null);
    try {
      const numeric = Object.fromEntries(
        numericFields.map(({ key }) => {
          const raw = values[key];
          // String vazia vira null: o campo não foi informado.
          return [key, raw === undefined || raw.trim() === "" ? null : Number(raw)];
        })
      );
      await createProject({ organization_id: organizationId, name, zone, ...numeric });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
      <div className="glass-panel rounded-2xl p-6 w-full max-w-2xl space-y-5 my-8">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white">Novo empreendimento</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <ErrorBanner error={error} />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Nome do empreendimento" required>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </Field>
            <Field label="Organização" required>
              <select
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Zona">
              <input
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </Field>
          </div>

          <p className="text-[11px] text-blue-300 pt-2">
            Deixe em branco o que ainda não souber. Campo vazio é registrado como
            &quot;não informado&quot; e gera verificação não verificável — o Atlas não
            assume zero.
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {numericFields.map(({ key, label }) => (
              <Field key={key} label={label}>
                <input
                  type="number"
                  step="any"
                  placeholder="não informado"
                  value={values[key] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none placeholder:text-slate-600 placeholder:text-[11px]"
                />
              </Field>
            ))}
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

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold text-slate-400 block mb-1.5">
        {label}
        {required && <span className="text-cyan-400"> *</span>}
      </span>
      {children}
    </label>
  );
}
