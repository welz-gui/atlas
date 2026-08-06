from app.core.database import SessionLocal, engine, Base
from app.models.domain import Organization, Project, User, Document, EAPItem, TaskItem, DailyLog
from app.services.regulatory_engine import RegulatoryEngine
import hashlib

def seed_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("Seeding updated data (EAP, Kanban & Daily Log)...")
    org = Organization(name="Construtora Delta & Atlas Demo", document_number="12.345.678/0001-90")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    user = User(
        organization_id=org.id,
        name="Engenheiro Responsável",
        email="engenharia@delta.com.br",
        role="engineer"
    )
    db.add(user)
    
    project1 = Project(
        organization_id=org.id,
        name="Residencial das Acácias (Lajeado Z2)",
        description="Residencial Unifamiliar 2 pavimentos em Lajeado - RS",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=450.0,
        built_area=240.0,
        floors=2,
        front_setback=4.50,
        side_setback=1.80,
        rear_setback=3.50,
        permeability_rate=22.5,
        parking_spaces=2,
        status="pre_analise",
        is_official_baseline=True
    )
    
    project2 = Project(
        organization_id=org.id,
        name="Residencial Sol Nascente (Alerta Recuo)",
        description="Projeto com inconsistência no recuo frontal para testes do Copiloto",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
        zone="Z2",
        building_type="residencial_unifamiliar",
        lot_area=360.0,
        built_area=220.0,
        floors=2,
        front_setback=3.20,
        side_setback=1.20,
        rear_setback=2.50,
        permeability_rate=12.0,
        parking_spaces=1,
        status="estudo_preliminar",
        is_official_baseline=False
    )
    
    project3 = Project(
        organization_id=org.id,
        name="Terreno Rua das Hortênsias (Cadastro Incompleto)",
        description="Cadastro sem medidas informadas — demonstra o estado 'não verificável'",
        city_ibge="BR-RS-4311403",
        city_name="Lajeado",
        state="RS",
        zone="Z2",
        building_type="residencial_unifamiliar",
        status="estudo_preliminar",
        is_official_baseline=False
    )

    db.add(project1)
    db.add(project2)
    db.add(project3)
    db.commit()
    
    # Avaliar regras regulatórias
    RegulatoryEngine.evaluate_project(db, project1, trigger="seed")
    RegulatoryEngine.evaluate_project(db, project2, trigger="seed")
    RegulatoryEngine.evaluate_project(db, project3, trigger="seed")

    # Documento de Exemplo
    sample_content = b"Prancha Arquitetonica v1.0 - Residencial das Acacias"
    doc_hash = hashlib.sha256(sample_content).hexdigest()
    
    doc1 = Document(
        project_id=project1.id,
        title="Prancha Arquitetônica de Implantação",
        category="projeto_arquitetonico",
        version="v1.0",
        file_path="0f4c1d7a9b2e4f0c8a6d5b3e1f7c9a2d.pdf",
        original_filename="acacias_implantacao.pdf",
        content_type="application/pdf",
        size_bytes=len(sample_content),
        hash_sha256=doc_hash,
        status="vigente"
    )
    db.add(doc1)
    
    # --- EAP Seed Data ---
    eap1 = EAPItem(project_id=project1.id, code="1.0", name="1. Serviços Preliminares e Canteiro", item_type="etapa", progress_percent=100.0)
    eap2 = EAPItem(project_id=project1.id, code="2.0", name="2. Infraestrutura e Fundações", item_type="etapa", progress_percent=75.0)
    eap3 = EAPItem(project_id=project1.id, code="3.0", name="3. Supraestrutura e Alvenaria", item_type="etapa", progress_percent=30.0)
    eap4 = EAPItem(project_id=project1.id, code="4.0", name="4. Instalações Hidrossanitárias e Elétricas", item_type="etapa", progress_percent=0.0)
    eap5 = EAPItem(project_id=project1.id, code="5.0", name="5. Acabamentos e Revestimentos", item_type="etapa", progress_percent=0.0)
    
    db.add_all([eap1, eap2, eap3, eap4, eap5])
    db.commit()

    # --- Kanban Tasks ---
    task1 = TaskItem(
        project_id=project1.id,
        eap_item_id=eap2.id,
        title="Concretagem das Vigas Baldrame (Eixo A-D)",
        description="Agendar caminhão betoneira e laudo de resistência Fck 30 MPa.",
        status="em_andamento",
        priority="alta",
        assignee="Eng. Carlos Silva",
        due_date="2026-08-12"
    )

    db.add(task1)
    db.commit()

    # --- Daily Logs Seed Data ---
    log1 = DailyLog(
        project_id=project1.id,
        date="2026-08-05",
        weather_condition="ensolarado",
        manpower_own=6,
        manpower_subcontracted=8,
        activities_done="Finalizada escavação das estacas do eixo B-C. Montagem das fôrmas do baldrame.",
        occurrences="Atraso de 30 minutos na entrega das barras de aço de 12mm.",
        status="assinado"
    )

    log2 = DailyLog(
        project_id=project1.id,
        date="2026-08-04",
        weather_condition="nublado",
        manpower_own=6,
        manpower_subcontracted=5,
        activities_done="Marcação gabarito de obra e nivelamento topográfico do lote.",
        occurrences="Nenhuma ocorrência registrada.",
        status="assinado"
    )

    db.add_all([log1, log2])
    db.commit()

    print("Seed concluído: 3 empreendimentos, análises regulatórias registradas.")
    db.close()

if __name__ == "__main__":
    seed_db()
