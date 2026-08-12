"""Semeia dados de demonstração.

Exige que as migrations já tenham sido aplicadas:

    alembic upgrade head && python seed.py
"""

import hashlib
from datetime import date, timedelta

from sqlalchemy import inspect

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models.domain import (
    DailyLog,
    Document,
    EAPItem,
    Organization,
    Project,
    ProjectVersionState,
    ProtocolProcess,
    ProtocolRequirement,
    RegulatoryDocument,
    RegulatoryDocumentState,
    TaskItem,
    User,
    UserRole,
)
from app.regulatory.importer import import_seed_catalog
from app.services import project_versions
from app.services.regulatory_engine import RegulatoryEngine

DEMO_PASSWORD = "atlas-demo-2026"




def _seed_regulatory_catalog(db):
    print("Semeando catálogo regulatório...")
    summary = import_seed_catalog(db)
    print(f"  regras: {summary['created']} criadas, {summary['updated']} atualizadas")

    # Documento regulatório catalogado, mas ainda não validado: nenhuma
    # regra é publicada automaticamente pelo seed (§7.5).
    db.add(
        RegulatoryDocument(
            jurisdiction="BR-RS-4311403",
            doc_type="plano_diretor",
            title="Plano Diretor de Lajeado",
            issuing_body="Prefeitura Municipal de Lajeado",
            state=RegulatoryDocumentState.CATALOGADO,
            theme="uso_e_ocupacao_do_solo",
        )
    )


def _seed_organization_and_users(db):
    print("Semeando organização e usuários...")
    org = Organization(
        name="Construtora Delta & Atlas Demo", document_number="12.345.678/0001-90"
    )
    db.add(org)
    db.flush()

    users = {
        "owner": User(
            organization_id=org.id, name="Guilherme (Responsável)",
            email="owner@atlas.demo", role=UserRole.OWNER,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        "validator": User(
            organization_id=org.id, name="Eng. Ana Validadora",
            email="validador@atlas.demo", role=UserRole.VALIDATOR,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        "engineer": User(
            organization_id=org.id, name="Eng. Carlos Silva",
            email="engenharia@atlas.demo", role=UserRole.ENGINEER,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        "client": User(
            organization_id=org.id, name="Cliente Demonstração",
            email="cliente@atlas.demo", role=UserRole.CLIENT,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
    }
    db.add_all(users.values())
    db.flush()
    return org, users


def _seed_projects(db, org, engineer):
    print("Semeando empreendimentos...")
    project1 = Project(
        organization_id=org.id,
        name="Residencial das Acácias",
        description="Residencial unifamiliar de 2 pavimentos em Lajeado/RS",
        address="Rua das Acácias", address_number="450", district="Centro",
        city_ibge="BR-RS-4311403", city_name="Lajeado", state="RS",
        lot="12", block="B", registry_number="M-45.221",
        owner_name="Construtora Delta Ltda.",
        technical_responsible_name="Eng. Carlos Silva",
        technical_responsible_registry="CREA-RS 123456",
        use_type="residencial_unifamiliar", units_count=1,
        created_by_id=engineer.id,
    )
    project2 = Project(
        organization_id=org.id,
        name="Residencial Sol Nascente",
        description="Projeto com inconsistências, para demonstrar bloqueios",
        address="Rua do Sol", address_number="88", district="Florestal",
        city_ibge="BR-RS-4311403", city_name="Lajeado", state="RS",
        use_type="residencial_unifamiliar", units_count=1,
        created_by_id=engineer.id,
    )
    project3 = Project(
        organization_id=org.id,
        name="Terreno Rua das Hortênsias",
        description="Cadastro sem medidas — demonstra o estado 'não verificável'",
        city_ibge="BR-RS-4311403", city_name="Lajeado", state="RS",
        created_by_id=engineer.id,
    )
    db.add_all([project1, project2, project3])
    db.flush()

    project_versions.create_version(
        db, project1,
        dict(zone="Z2", building_type="residencial_unifamiliar", lot_area=450.0,
             built_area=240.0, floors=2, front_setback=4.50, side_setback=1.80,
             rear_setback=3.50, permeability_rate=22.5, parking_spaces=2),
        user=engineer, change_reason="Cadastro inicial.", commit=False,
    )
    project_versions.create_version(
        db, project2,
        dict(zone="Z2", building_type="residencial_unifamiliar", lot_area=360.0,
             built_area=220.0, floors=2, front_setback=3.20, side_setback=1.20,
             rear_setback=2.50, permeability_rate=12.0, parking_spaces=1),
        user=engineer, change_reason="Cadastro inicial.", commit=False,
    )
    project_versions.create_version(
        db, project3, dict(zone="Z2", building_type="residencial_unifamiliar"),
        user=engineer, change_reason="Cadastro inicial, sem medidas.", commit=False,
    )
    db.commit()

    for project in (project1, project2, project3):
        db.refresh(project)
        RegulatoryEngine.evaluate_project(db, project, trigger="seed", user=engineer)

    return project1, project2, project3


def _seed_documents_and_processes(db, org, engineer, project1, project2):
    print("Semeando documento, tramitação e obra...")
    sample = b"Prancha arquitetonica v1.0 - Residencial das Acacias"
    db.add(
        Document(
            organization_id=org.id, project_id=project1.id,
            project_version_id=project1.current_version.id,
            title="Prancha Arquitetônica de Implantação",
            category="projeto_arquitetonico", version="v1.0",
            file_path="0f4c1d7a9b2e4f0c8a6d5b3e1f7c9a2d.pdf",
            original_filename="acacias_implantacao.pdf",
            content_type="application/pdf", size_bytes=len(sample),
            hash_sha256=hashlib.sha256(sample).hexdigest(),
            status="vigente", uploaded_by_id=engineer.id,
        )
    )

    # Tramitação do projeto com inconsistências: uma exigência real que o
    # motor havia antecipado e outra que não.
    version2 = project2.current_version
    version2.state = ProjectVersionState.PROTOCOLADA
    process = ProtocolProcess(
        organization_id=org.id, project_id=project2.id,
        project_version_id=version2.id,
        protocol_number="2026/PMU-004821",
        agency="Secretaria de Planejamento — Lajeado/RS",
        status="notificado",
        submitted_at=str(date.today() - timedelta(days=21)),
    )
    db.add(process)
    db.flush()

    db.add_all([
        ProtocolRequirement(
            organization_id=org.id, process_id=process.id, sequence=1,
            description="Ajustar o recuo frontal ao mínimo exigido para a zona.",
            raised_at=str(date.today() - timedelta(days=7)),
            due_date=str(date.today() + timedelta(days=23)),
            linked_rule_key="lajeado_recuo_frontal_z2", was_predicted=True,
        ),
        ProtocolRequirement(
            organization_id=org.id, process_id=process.id, sequence=2,
            description="Apresentar ART/RRT do responsável técnico assinada.",
            raised_at=str(date.today() - timedelta(days=7)),
            due_date=str(date.today() + timedelta(days=23)),
        ),
    ])
    project2.licensing_status = "notificado"


def _seed_construction_management(db, org, engineer, project1):
    eap_items = [
        EAPItem(organization_id=org.id, project_id=project1.id, code="1.0",
                name="1. Serviços Preliminares e Canteiro", progress_percent=100.0),
        EAPItem(organization_id=org.id, project_id=project1.id, code="2.0",
                name="2. Infraestrutura e Fundações", progress_percent=75.0),
        EAPItem(organization_id=org.id, project_id=project1.id, code="3.0",
                name="3. Supraestrutura e Alvenaria", progress_percent=30.0),
        EAPItem(organization_id=org.id, project_id=project1.id, code="4.0",
                name="4. Instalações Hidrossanitárias e Elétricas"),
        EAPItem(organization_id=org.id, project_id=project1.id, code="5.0",
                name="5. Acabamentos e Revestimentos"),
    ]
    db.add_all(eap_items)
    db.flush()

    db.add(
        TaskItem(
            organization_id=org.id, project_id=project1.id,
            eap_item_id=eap_items[1].id,
            title="Concretagem das vigas baldrame (eixo A-D)",
            description="Agendar caminhão betoneira e laudo de resistência Fck 30 MPa.",
            status="em_andamento", priority="alta", assignee="Eng. Carlos Silva",
            due_date=str(date.today() + timedelta(days=6)),
            created_by_id=engineer.id,
        )
    )
    db.add_all([
        DailyLog(
            organization_id=org.id, project_id=project1.id,
            date=str(date.today() - timedelta(days=1)),
            weather_condition="ensolarado", manpower_own=6, manpower_subcontracted=8,
            activities_done="Finalizada escavação das estacas do eixo B-C. "
                            "Montagem das fôrmas do baldrame.",
            occurrences="Atraso de 30 minutos na entrega das barras de aço de 12mm.",
            created_by_id=engineer.id,
        ),
        DailyLog(
            organization_id=org.id, project_id=project1.id,
            date=str(date.today() - timedelta(days=2)),
            weather_condition="nublado", manpower_own=6, manpower_subcontracted=5,
            activities_done="Marcação do gabarito de obra e nivelamento topográfico.",
            occurrences="Nenhuma ocorrência registrada.",
            created_by_id=engineer.id,
        ),
    ])
    db.commit()


def seed_db() -> None:
    if "alembic_version" not in inspect(engine).get_table_names():
        raise SystemExit(
            "Banco sem migrations aplicadas. Rode `alembic upgrade head` antes do seed."
        )

    db = SessionLocal()
    try:
        if db.query(Organization).count():
            raise SystemExit(
                "O banco já contém dados. Para recriar do zero: "
                "rm atlas_dev.db && alembic upgrade head && python seed.py"
            )

        _seed_regulatory_catalog(db)
        org, users = _seed_organization_and_users(db)
        engineer = users["engineer"]

        project1, project2, project3 = _seed_projects(db, org, engineer)
        _seed_documents_and_processes(db, org, engineer, project1, project2)
        _seed_construction_management(db, org, engineer, project1)

        print("\nSeed concluído.")
        print(f"  Acesso de demonstração — senha: {DEMO_PASSWORD}")
        for role, user in users.items():
            print(f"    {user.email:26} {role}")
        print("\n  O catálogo permanece EM VALIDAÇÃO: nenhuma regra foi publicada.")
        print("  Entre como validador@atlas.demo para conferir e publicar regras.")
    finally:
        db.close()
if __name__ == "__main__":
    seed_db()
