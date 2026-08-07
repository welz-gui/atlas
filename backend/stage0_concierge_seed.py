"""Script de execução do Estágio 0 (Concierge) — Atlas.

Cadastra 5 cenários reais de pré-análises de Lajeado/RS, valida o catálogo
regulatório com artigos oficiais, executa o motor de conformidade e simula a
tramitação de protocolos com exigências do órgão para medição de acurácia.

Uso:
    python stage0_concierge_seed.py
"""

from datetime import date, datetime, timezone, timedelta
from sqlalchemy import inspect

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
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
    RuleValidationEvent,
)
from app.regulatory.catalog import RuleState
from app.regulatory.importer import import_seed_catalog
from app.services import project_versions
from app.services.regulatory_engine import RegulatoryEngine

DEMO_PASSWORD = "atlas-concierge-2026"


def run_stage0_seed():
    if "alembic_version" not in inspect(engine).get_table_names():
        raise SystemExit("Banco sem migrations. Rode `alembic upgrade head` primeiro.")

    db = SessionLocal()
    try:
        print("1. Atualizando e reimportando catálogo regulatório de Lajeado/RS...")
        summary = import_seed_catalog(db)
        print(f"   Catálogo: {summary['created']} criadas, {summary['updated']} atualizadas.")

        # Garantir registro do documento regulatório
        doc_lajeado = db.query(RegulatoryDocument).filter_by(jurisdiction="BR-RS-4311403").first()
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
        org = db.query(Organization).filter_by(document_number="99.888.777/0001-10").first()
        if not org:
            org = Organization(
                name="Atlas Concierge Lajeado (Estágio 0)",
                document_number="99.888.777/0001-10",
            )
            db.add(org)
            db.flush()

        # Usuários
        validador = db.query(User).filter_by(email="validador.concierge@atlas.demo").first()
        if not validador:
            validador = User(
                organization_id=org.id,
                name="Eng. Validadora Técnica (Lajeado)",
                email="validador.concierge@atlas.demo",
                role=UserRole.VALIDATOR,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(validador)

        analista = db.query(User).filter_by(email="analista.concierge@atlas.demo").first()
        if not analista:
            analista = User(
                organization_id=org.id,
                name="Eng. Analista Concierge",
                email="analista.concierge@atlas.demo",
                role=UserRole.ENGINEER,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(analista)

        db.flush()

        print("3. Validação e promoção das regras de Lajeado para VIGENTE (pelo validador humano)...")
        now_utc = datetime.now(timezone.utc)
        official_sources = {
            "lajeado_recuo_frontal_z2": ("Lei Complementar nº 002/2014 — Plano Diretor de Lajeado", "Art. 45"),
            "lajeado_taxa_ocupacao_max_z2": ("Lei Complementar nº 002/2014 — Plano Diretor de Lajeado", "Anexo II"),
            "lajeado_recuo_fundos_z2": ("Lei Complementar nº 002/2014 — Plano Diretor de Lajeado", "Art. 48"),
            "lajeado_taxa_permeabilidade_min_z2": ("Lei Complementar nº 001/2014 — Código de Edificações", "Art. 32"),
            "lajeado_gabarito_maximo_z2": ("Lei Complementar nº 002/2014 — Plano Diretor de Lajeado", "Art. 50"),
            "lajeado_vagas_estacionamento": ("Lei Complementar nº 001/2014 — Código de Edificações", "Art. 88"),
            "lajeado_acessibilidade_nbr9050": ("ABNT NBR 9050:2020 / Lei Federal 13.146/2015", "Art. 56"),
        }

        regras_lajeado = db.query(RegulatoryRule).filter_by(jurisdiction="BR-RS-4311403").all()
        for regra in regras_lajeado:
            if regra.rule_key in official_sources:
                doc_title, art_title = official_sources[regra.rule_key]
                regra.source_document = doc_title
                regra.source_article = art_title
                regra.state = RuleState.VIGENTE
                regra.effective_from = "2026-01-01"
                regra.validated_by_id = validador.id
                regra.validated_at = now_utc
                db.add(
                    RuleValidationEvent(
                        rule_id=regra.id,
                        from_state=RuleState.EM_VALIDACAO,
                        to_state=RuleState.VIGENTE,
                        action="publicar",
                        actor_id=validador.id,
                        actor_name=validador.name,
                        notes=f"Conferido com {doc_title} ({art_title}) durante o Estágio 0.",
                    )
                )
        doc_lajeado.state = RegulatoryDocumentState.VALIDADO
        db.commit()

        print("4. Cadastrando 5 cenários reais do Estágio 0 (Concierge Lajeado)...")

        scenarios = [
            {
                "name": "Concierge #1: Residencial Bela Vista",
                "desc": "Residencial unifamiliar de 2 pavimentos na Zona Z2 — Projeto 100% Conforme",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2", building_type="residencial_unifamiliar", lot_area=450.0,
                    built_area=225.0, floors=2, front_setback=4.50, side_setback=1.80,
                    rear_setback=3.50, permeability_rate=20.0, parking_spaces=2
                ),
                "requirements": []
            },
            {
                "name": "Concierge #2: Residencial Jardim Florestal",
                "desc": "Residencial unifamiliar com recuo frontal insuficiente (3.5m vs 4.0m)",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2", building_type="residencial_unifamiliar", lot_area=380.0,
                    built_area=210.0, floors=2, front_setback=3.50, side_setback=1.50,
                    rear_setback=3.20, permeability_rate=18.0, parking_spaces=1
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Ajustar o recuo frontal ao mínimo de 4,00m conforme Art. 45 do Plano Diretor.",
                        "rule": "lajeado_recuo_frontal_z2",
                        "predicted": True
                    }
                ]
            },
            {
                "name": "Concierge #3: Residencial San José",
                "desc": "Residencial geminado com taxa de ocupação excedida (65% vs 60% max)",
                "use_type": "residencial_geminado",
                "params": dict(
                    zone="Z2", building_type="residencial_geminado", lot_area=300.0,
                    built_area=195.0, floors=2, front_setback=4.00, side_setback=1.50,
                    rear_setback=3.00, permeability_rate=16.0, parking_spaces=2
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Taxa de ocupação de 65% excede o limite máximo de 60% da Zona Z2.",
                        "rule": "lajeado_taxa_ocupacao_max_z2",
                        "predicted": True
                    }
                ]
            },
            {
                "name": "Concierge #4: Residencial Montanha",
                "desc": "Projeto conforme nos parâmetros, mas notificado por documento complementar do órgão",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2", building_type="residencial_unifamiliar", lot_area=500.0,
                    built_area=240.0, floors=2, front_setback=4.20, side_setback=2.00,
                    rear_setback=4.00, permeability_rate=25.0, parking_spaces=2
                ),
                "requirements": [
                    {
                        "seq": 1,
                        "desc": "Apresentar laudo de sondagem de solo e parecer de esgotamento sanitário.",
                        "rule": None,
                        "predicted": False
                    }
                ]
            },
            {
                "name": "Concierge #5: Terreno Alto do Parque",
                "desc": "Cadastro preliminar com dados incompletos — demonstra o estado 'não verificável'",
                "use_type": "residencial_unifamiliar",
                "params": dict(
                    zone="Z2", building_type="residencial_unifamiliar", lot_area=400.0
                ),
                "requirements": []
            }
        ]

        created_projects = []
        for index, sc in enumerate(scenarios, start=1):
            proj = db.query(Project).filter_by(organization_id=org.id, name=sc["name"]).first()
            if not proj:
                proj = Project(
                    organization_id=org.id,
                    name=sc["name"],
                    description=sc["desc"],
                    city_ibge="BR-RS-4311403",
                    city_name="Lajeado",
                    state="RS",
                    use_type=sc["use_type"],
                    created_by_id=analista.id
                )
                db.add(proj)
                db.flush()

                # Versão inicial
                project_versions.create_version(
                    db, proj, sc["params"],
                    user=analista,
                    change_reason=f"Cadastro de Pré-análise Concierge #{index}",
                    commit=False
                )
                db.flush()

            # Executa a pré-análise pelo motor regulatório
            db.refresh(proj)
            RegulatoryEngine.evaluate_project(db, proj, trigger=f"concierge_v{index}", user=analista)

            # Cadastra protocolo e exigências se houver
            if sc["requirements"]:
                proj.current_version.state = ProjectVersionState.PROTOCOLADA
                process = db.query(ProtocolProcess).filter_by(project_id=proj.id).first()
                if not process:
                    process = ProtocolProcess(
                        organization_id=org.id,
                        project_id=proj.id,
                        project_version_id=proj.current_version.id,
                        protocol_number=f"2026/PMU-0090{index}",
                        agency="Secretaria de Planejamento e Urbanismo — Lajeado/RS",
                        status="notificado",
                        submitted_at=str(date.today() - timedelta(days=10))
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
                                was_predicted=req["predicted"]
                            )
                        )

            created_projects.append(proj)

        db.commit()
        print(f"[OK] Sucesso! 5 projetos do Estágio 0 (Concierge) semeados e analisados para a Org '{org.name}'.")

    finally:
        db.close()


if __name__ == "__main__":
    run_stage0_seed()
