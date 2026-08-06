from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.domain import Project, ValidationRecord

# Regras cadastradas para o Município de Lajeado (BR-RS-4311403)
LAJEADO_RULES = [
    {
        "rule_id": "lajeado_recuo_frontal_z2",
        "rule_title": "Recuo Frontal Mínimo - Zona Z2",
        "field": "front_setback",
        "check": lambda p: p.front_setback >= 4.0 if p.zone == "Z2" else True,
        "expected": ">= 4.00m",
        "get_actual": lambda p: f"{p.front_setback:.2f}m",
        "citation": "Plano Diretor de Lajeado, Art. 45 (Zona Z2)",
        "applies": lambda p: p.zone == "Z2" and p.city_ibge == "BR-RS-4311403"
    },
    {
        "rule_id": "lajeado_taxa_ocupacao_max_z2",
        "rule_title": "Taxa de Ocupação Máxima - Zona Z2",
        "field": "occupancy_rate",
        "check": lambda p: (p.built_area / p.lot_area * 100 <= 60.0) if (p.lot_area > 0 and p.zone == "Z2") else (p.occupancy_rate <= 60.0),
        "expected": "<= 60.0%",
        "get_actual": lambda p: f"{(p.built_area / p.lot_area * 100):.1f}%" if p.lot_area > 0 else f"{p.occupancy_rate:.1f}%",
        "citation": "Plano Diretor de Lajeado, Tabela de Zoneamento Z2",
        "applies": lambda p: p.zone == "Z2" and p.city_ibge == "BR-RS-4311403"
    },
    {
        "rule_id": "lajeado_recuo_fundos_z2",
        "rule_title": "Recuo dos Fundos Mínimo - Zona Z2",
        "field": "rear_setback",
        "check": lambda p: p.rear_setback >= 3.00 if p.zone == "Z2" else True,
        "expected": ">= 3.00m",
        "get_actual": lambda p: f"{p.rear_setback:.2f}m",
        "citation": "Plano Diretor de Lajeado, Art. 46 (Zona Z2)",
        "applies": lambda p: p.zone == "Z2" and p.city_ibge == "BR-RS-4311403"
    },
    {
        "rule_id": "lajeado_taxa_permeabilidade_min_z2",
        "rule_title": "Taxa de Permeabilidade Mínima - Zona Z2",
        "field": "permeability_rate",
        "check": lambda p: p.permeability_rate >= 15.0 if p.zone == "Z2" else True,
        "expected": ">= 15.0%",
        "get_actual": lambda p: f"{p.permeability_rate:.1f}%",
        "citation": "Código de Edificações de Lajeado, Art. 38",
        "applies": lambda p: p.zone == "Z2" and p.city_ibge == "BR-RS-4311403"
    },
    {
        "rule_id": "lajeado_gabarito_maximo_z2",
        "rule_title": "Gabarito Máximo de Pavimentos - Residencial Z2",
        "field": "floors",
        "check": lambda p: p.floors <= 3 if (p.building_type in ["residencial_unifamiliar", "residencial_geminado"]) else True,
        "expected": "<= 3 pavimentos",
        "get_actual": lambda p: f"{p.floors} pavimentos",
        "citation": "Plano Diretor de Lajeado, Art. 52",
        "applies": lambda p: p.zone == "Z2" and p.building_type in ["residencial_unifamiliar", "residencial_geminado"]
    },
    {
        "rule_id": "lajeado_vagas_estacionamento",
        "rule_title": "Vagas de Garagem / Estacionamento Mínimo",
        "field": "parking_spaces",
        "check": lambda p: p.parking_spaces >= 1,
        "expected": ">= 1 vaga",
        "get_actual": lambda p: f"{p.parking_spaces} vaga(s)",
        "citation": "Código de Edificações de Lajeado, Art. 55",
        "applies": lambda p: True
    },
    {
        "rule_id": "lajeado_acessibilidade_nbr9050",
        "rule_title": "Conformidade NBR 9050 (Acessibilidade e Rota Acessível)",
        "field": "accessibility_check",
        "check": lambda p: None, # Requer upload de arquivo de projeto
        "expected": "Laudo Acessibilidade / Prancha ARQ",
        "get_actual": "Pendente de análise gráfica",
        "citation": "ABNT NBR 9050 / Lei Federal de Acessibilidade",
        "applies": lambda p: True
    }
]

class RegulatoryEngine:
    @staticmethod
    def evaluate_project(db: Session, project: Project) -> List[ValidationRecord]:
        # Limpar verificações anteriores do projeto
        db.query(ValidationRecord).filter(ValidationRecord.project_id == project.id).delete()
        
        records = []
        for rule in LAJEADO_RULES:
            if not rule["applies"](project):
                continue
                
            check_result = rule["check"](project)
            actual_val = rule["get_actual"](project) if callable(rule["get_actual"]) else str(rule["get_actual"])
            
            if check_result is None:
                status = "nao_verificavel"
                details = "Necessita upload de arquivo de projeto (IFC/PDF) na aba 'Projetos e Documentos' para medição assistida."
            elif check_result is True:
                status = "conforme"
                details = "Parâmetro dentro do limite exigido pela norma municipal vigente."
            else:
                status = "nao_conforme"
                details = f"O valor informado ({actual_val}) viola o limite especificado ({rule['expected']})."
                
            record = ValidationRecord(
                project_id=project.id,
                rule_id=rule["rule_id"],
                rule_title=rule["rule_title"],
                status=status,
                field=rule["field"],
                expected_value=rule["expected"],
                actual_value=actual_val,
                details=details,
                source_citation=rule["citation"]
            )
            db.add(record)
            records.append(record)
            
        db.commit()
        return records
