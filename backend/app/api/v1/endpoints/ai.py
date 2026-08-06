from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import Project

router = APIRouter()

class AIChatRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None

class AIChatResponse(BaseModel):
    answer: str
    law_citations: List[str]
    suggested_actions: List[str]

# Lajeado / RS Regulatory Knowledge Base Context
KNOWLEDGE_BASE = {
    "recuo_frontal": "Art. 42 do Código de Edificações de Lajeado/RS: Para zonas Z2, o recuo frontal mínimo obrigatório é de 4,00m a contar do alinhamento predial.",
    "taxa_ocupacao": "Art. 35 do Plano Diretor de Lajeado/RS: A Taxa de Ocupação Máxima para zona residencial unifamiliar Z2 é de 60%. Área construída no pavimento térreo não deve exceder 60% da área total do lote.",
    "recuo_fundos": "Art. 45 do Código de Edificações: O recuo dos fundos mínimo é de 3,00m para edifícios de até 2 pavimentos.",
    "permeabilidade": "Art. 50 do Código Ambiental Municipal: A Taxa de Permeabilidade mínima é de 15% (ou 20% dependendo do tipo de piso drenante).",
    "estacionamento": "Art. 60 da Lei de Zoneamento: Mínimo de 1 vaga de garagem coberta ou descoberta por unidade residencial unifamiliar.",
    "nbr_9050": "NBR 9050/2020: Garante acessibilidade a pessoas com deficiência. Exige rampa de acesso com inclinação máxima de 8,33% e portas com largura útil mínima de 0,80m."
}

@router.post("/ai/chat", response_model=AIChatResponse)
def atlas_ai_chat(req: AIChatRequest, db: Session = Depends(get_db)):
    prompt_lower = req.prompt.lower()
    
    project_info = ""
    if req.project_id:
        project = db.query(Project).filter(Project.id == req.project_id).first()
        if project:
            project_info = f"Empreendimento Analisado: '{project.name}' (Zona {project.zone}, Lote: {project.lot_area}m², Área Construída: {project.built_area}m²)."

    citations = []
    actions = []
    
    if "recuo" in prompt_lower or "frontal" in prompt_lower:
        citations.append(KNOWLEDGE_BASE["recuo_frontal"])
        citations.append(KNOWLEDGE_BASE["recuo_fundos"])
        actions.append("Ajustar o recuo frontal do projeto para no mínimo 4,00m.")
        actions.append("Verificar afastamento dos fundos de no mínimo 3,00m.")
    
    if "taxa" in prompt_lower or "ocupacao" in prompt_lower or "ocupação" in prompt_lower:
        citations.append(KNOWLEDGE_BASE["taxa_ocupacao"])
        actions.append("Reduzir a projeção do pavimento térreo para não ultrapassar 60% da área do lote.")
    
    if "permeabilidade" in prompt_lower or "solo" in prompt_lower:
        citations.append(KNOWLEDGE_BASE["permeabilidade"])
        actions.append("Especificar piso intertravado drenante ou área verde de no mínimo 15%.")
        
    if "vagas" in prompt_lower or "estacionamento" in prompt_lower or "garagem" in prompt_lower:
        citations.append(KNOWLEDGE_BASE["estacionamento"])
        actions.append("Garantir pelo menos 1 vaga de estacionamento livre com dimensões mínimas de 2,40m x 5,00m.")

    if "acessibilidade" in prompt_lower or "nbr" in prompt_lower or "rampa" in prompt_lower:
        citations.append(KNOWLEDGE_BASE["nbr_9050"])
        actions.append("Adicionar rampa com inclinação de 8.33% no acesso principal.")

    if not citations:
        citations.append("Código de Edificações e Plano Diretor do Município de Lajeado / RS (Lei Complementar Vigente).")
        actions.append("Consulte o Copiloto de Aprovações para simular parâmetros específicos em tempo real.")

    answer = f"Com base na legislação urbanística municipal de Lajeado/RS"
    if project_info:
        answer += f" e no contexto do {project_info}"
    answer += ":\n\n"
    
    if "recuo" in prompt_lower:
        answer += "Para a zona Z2, os recuos são obrigatórios. O recuo frontal não pode ser inferior a 4,00m e o recuo dos fundos deve respeitar o mínimo de 3,00m."
    elif "taxa" in prompt_lower or "ocupacao" in prompt_lower:
        answer += "A Taxa de Ocupação limite é de 60%. Caso seu projeto exceda esse valor, será apontado como 'NÃO CONFORME' durante o protocolo municipal."
    elif "permeabilidade" in prompt_lower:
        answer += "A taxa de permeabilidade exige pelo menos 15% do solo livre de pavimentação impermeável."
    else:
        answer += f"Analisando sua consulta '{req.prompt}': Todos os parâmetros urbanísticos do município de Lajeado/RS estão mapeados de forma determinística no motor regulatório do Atlas."

    return AIChatResponse(
        answer=answer,
        law_citations=citations,
        suggested_actions=actions
    )
