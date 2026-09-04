"""Ambiente de demonstração do Estágio 0 (Concierge) — Atlas.

Prepara uma organização, os usuários do concierge e cinco cenários de
**demonstração** em Lajeado/RS, roda o motor sobre cada um e monta a tramitação
que exercita a medição de acurácia (§11).

O que este script **não** faz, por desenho:

- **não publica regra.** O catálogo é importado e permanece como está — as
  regras de Lajeado seguem em `em_validacao`, sem artigo, sem validador. Promover
  regra a `vigente` é ato humano, feito na tela `/catalog` por quem conferiu o
  texto legal, e fica registrado em `rule_validation_events` com o nome de quem
  conferiu (§7.5). Script nenhum tem como fazer isso sem forjar essa trilha;
- **não preenche `source_article`.** Número de artigo entra quando alguém abriu
  a lei publicada, nunca a partir de um dicionário aqui dentro;
- **não afirma `was_predicted`.** O valor é derivado do que o motor de fato
  apontou na análise, não escrito à mão — do contrário o recall devolveria a
  nossa própria suposição com aparência de medição.

Consequência esperada e correta: os laudos destes cenários saem
`is_publishable=False`, marcados como uso interno, e o portal do cliente omite o
resumo de conformidade. É o sistema se recusando a entregar número não
conferido. Para vê-lo publicar, confira o catálogo de verdade.

Os projetos aqui são **fictícios**, para exercitar a ferramenta. Os projetos
reais do Estágio 0 entram pela interface, como qualquer análise paga.

Uso:
    python stage0_concierge_seed.py
"""

import os
import secrets
from datetime import date, timedelta
from sqlalchemy import inspect

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.schemas.domain import ProjectParameters
from app.models.domain import (
    Organization,
    User,
    UserRole,
    Project,
    ProjectVersionState,
    ProtocolProcess,
    ProtocolRequirement,
    RegulatoryDocument,
    RegulatoryDocumentState,
    RegulatoryRule,
)
from app.regulatory.catalog import CheckOutcome, RuleState
from app.regulatory.importer import import_seed_catalog
from app.services import project_versions
from app.services.regulatory_engine import RegulatoryEngine

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", secrets.token_urlsafe(16))

#: Resultados que contam como "o Atlas apontou isto antes do órgão".
APONTADO = (CheckOutcome.NAO_CONFORME, CheckOutcome.ATENCAO)


def run_stage0_seed():
    if "alembic_version" not in inspect(engine).get_table_names():
        raise SystemExit("Banco sem migrations. Rode `alembic upgrade head` primeiro.")

    db = SessionLocal()
    try:
        print("1. Atualizando e reimportando catálogo regulatório de Lajeado/RS...")
        summary = import_seed_catalog(db)
        print(
            f"   Catálogo: {summary['created']} criadas, {summary['updated']} atualizadas."
        )

        # Garantir registro do documento regulatório
        doc_lajeado = (
            db.query(RegulatoryDocument).filter_by(jurisdiction="BR-RS-4311403").first()
        )
        if not doc_lajeado:
            doc_lajeado = RegulatoryDocument(
                jurisdiction="BR-RS-4311403",
                doc_type="plano_diretor",
                title="Plano Diretor e Código de Edificações de Lajeado/RS",
                issuing_body="Prefeitura Municipal de Lajeado",
                state=RegulatoryDocumentState.CATALOGADO,
                theme="uso_e_ocupacao_do_solo",
            )
            db.add(doc_lajeado)
            db.flush()

        print("2. Criando/Recuperando organização e usuários do Concierge...")
        org = (
            db.query(Organization)
            .filter_by(document_number="99.888.777/0001-10")
            .first()
        )
        if not org:
            org = Organization(
                name="Atlas Concierge Lajeado (Estágio 0)",
                document_number="99.888.777/0001-10",
            )
            db.add(org)
            db.flush()

        # Usuários
        validador = (
            db.query(User).filter_by(email="validador.concierge@atlas.demo").first()
        )
        if not validador:
            validador = User(
                organization_id=org.id,
                name="Eng. Validadora Técnica (Lajeado)",
                email="validador.concierge@atlas.demo",
                role=UserRole.VALIDATOR,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(validador)

        analista = (
            db.query(User).filter_by(email="analista.concierge@atlas.demo").first()
        )
        if not analista:
            analista = User(
                organization_id=org.id,
                name="Eng. Analista Concierge",
                email="analista.concierge@atlas.demo",
                role=UserRole.ENGINEER,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(analista)

        db.commit()

        print(
            "3. Conferindo o estado do catálogo (nenhuma regra é publicada por aqui)..."
        )
        regras_lajeado = (
            db.query(RegulatoryRule).filter_by(jurisdiction="BR-RS-4311403").all()
        )
        pendentes = [r for r in regras_lajeado if r.state != RuleState.VIGENTE]
        print(
            f"   {len(regras_lajeado)} regras de Lajeado, {len(pendentes)} aguardando conferência humana."
        )
        if pendentes:
            print(
                f"   Publique-as em /catalog, como '{validador.email}', depois de conferir o texto legal."
            )

        print("4. Cadastrando 5 cenários de demonstração (Concierge Lajeado)...")

        scenarios = [
            {
                "name": "Concierge #1: Residencial Bela Vista",
                "desc": "Residencial unifamiliar de 2 pavimentos na Zona Z2 — Projeto 100% Conforme",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2",
                    building_type="residencial_unifamiliar",
                    lot_area=450.0,
                    built_area=225.0,
                    floors=2,
                    front_setback=4.50,
                    side_setback=1.80,
                    rear_setback=3.50,
                    permeability_rate=20.0,
                    parking_spaces=2,
                ),
                "requirements": [],
            },
            {
                "name": "Concierge #2: Residencial Jardim Florestal",
                "desc": "Residencial unifamiliar com recuo frontal insuficiente (3.5m vs 4.0m)",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2",
                    building_type="residencial_unifamiliar",
                    lot_area=380.0,
                    built_area=210.0,
                    floors=2,
                    front_setback=3.50,
                    side_setback=1.50,
                    rear_setback=3.20,
                    permeability_rate=18.0,
                    parking_spaces=1,
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Ajustar o recuo frontal ao mínimo exigido para a Zona Z2.",
                        "rule": "lajeado_recuo_frontal_z2",
                    }
                ],
            },
            {
                "name": "Concierge #3: Residencial San José",
                "desc": "Residencial geminado com taxa de ocupação excedida (65% vs 60% max)",
                "use_type": "residencial_geminado",
                "params": dict(
                    zone="Z2",
                    building_type="residencial_geminado",
                    lot_area=300.0,
                    built_area=195.0,
                    floors=2,
                    front_setback=4.00,
                    side_setback=1.50,
                    rear_setback=3.00,
                    permeability_rate=16.0,
                    parking_spaces=2,
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Taxa de ocupação acima do limite máximo da Zona Z2.",
                        "rule": "lajeado_taxa_ocupacao_max_z2",
                    }
                ],
            },
            {
                "name": "Concierge #4: Residencial Montanha",
                "desc": "Projeto conforme nos parâmetros, mas notificado por documento complementar do órgão",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2",
                    building_type="residencial_unifamiliar",
                    lot_area=500.0,
                    built_area=240.0,
                    floors=2,
                    front_setback=4.20,
                    side_setback=2.00,
                    rear_setback=4.00,
                    permeability_rate=25.0,
                    parking_spaces=2,
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Apresentar laudo de sondagem de solo e parecer de esgotamento sanitário.",
                        "rule": None,
                    }
                ],
            },
            {
                "name": "Concierge #5: Terreno Alto do Parque",
                "desc": "Cadastro preliminar com dados incompletos — demonstra o estado 'não verificável'",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2", building_type="residencial_unifamiliar", lot_area=400.0
                ),
                "requirements": [],
            },
        ]

        created_projects = []
        created_runs = []
        for index, sc in enumerate(scenarios, start=1):
            proj = (
                db.query(Project)
                .filter_by(organization_id=org.id, name=sc["name"])
                .first()
            )
            if not proj:
                proj = Project(
                    organization_id=org.id,
                    name=sc["name"],
                    description=sc["desc"],
                    city_ibge="BR-RS-4311403",
                    city_name="Lajeado",
                    state="RS",
                    use_type=sc["use_type"],
                    created_by_id=analista.id,
                )
                db.add(proj)
                db.flush()

                # Versão inicial
                project_versions.create_version(
                    db,
                    proj,
                    ProjectParameters(**sc["params"]),
                    user=analista,
                    change_reason=f"Cadastro de Pré-análise Concierge #{index}",
                    commit=False,
                )
                db.flush()

            # Executa a pré-análise pelo motor regulatório
            db.refresh(proj)
            run = RegulatoryEngine.evaluate_project(
                db, proj, trigger=f"concierge_v{index}", user=analista
            )

            # Regras que o motor de fato apontou nesta análise. É daqui que sai
            # `was_predicted` — afirmá-lo à mão faria o recall medir a nossa
            # expectativa em vez do desempenho do motor.
            apontadas = {v.rule_id for v in run.validations if v.status in APONTADO}

            # Cadastra protocolo e exigências se houver
            if sc["requirements"]:
                proj.current_version.state = ProjectVersionState.PROTOCOLADA
                process = (
                    db.query(ProtocolProcess).filter_by(project_id=proj.id).first()
                )
                if not process:
                    process = ProtocolProcess(
                        organization_id=org.id,
                        project_id=proj.id,
                        project_version_id=proj.current_version.id,
                        protocol_number=f"2026/PMU-0090{index}",
                        agency="Secretaria de Planejamento e Urbanismo — Lajeado/RS",
                        status="notificado",
                        submitted_at=str(date.today() - timedelta(days=10)),
                    )
                    db.add(process)
                    db.flush()

                    for req in sc["requirements"]:
                        db.add(
                            ProtocolRequirement(
                                organization_id=org.id,
                                process_id=process.id,
                                sequence=req["seq"],
                                description=req["desc"],
                                raised_at=str(date.today() - timedelta(days=3)),
                                due_date=str(date.today() + timedelta(days=27)),
                                linked_rule_key=req["rule"],
                                was_predicted=bool(req["rule"])
                                and req["rule"] in apontadas,
                            )
                        )

            created_projects.append(proj)
            created_runs.append(run)

        db.commit()

        publicaveis = sum(1 for r in created_runs if r.is_publishable)
        print(
            f"[OK] {len(created_projects)} cenários de demonstração semeados e analisados "
            f"para a organização '{org.name}'."
        )
        print(f"     Laudos publicáveis: {publicaveis} de {len(created_runs)}.")
        if publicaveis < len(created_runs):
            print(
                "     Os demais saem marcados como uso interno porque aplicam regra ainda\n"
                "     não conferida — comportamento esperado (§7.5). Confira o catálogo em\n"
                "     /catalog para que passem a ser publicáveis."
            )
        print(f"     Acesso de demonstração — senha: {DEMO_PASSWORD}")

    finally:
        db.close()


if __name__ == "__main__":
    run_stage0_seed()
